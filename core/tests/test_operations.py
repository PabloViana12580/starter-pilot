"""F5 operations: probes, security logging, CSP reports, error pages."""

import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import OperationalError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import path, reverse

User = get_user_model()
PASSWORD = 'correct-Horse-battery-42'


class ProbeTests(TestCase):
    def test_liveness_needs_no_database(self):
        with mock.patch('django.db.backends.base.base.BaseDatabaseWrapper.cursor', side_effect=OperationalError):
            response = self.client.get('/healthz')
        self.assertEqual((response.status_code, response.content), (200, b'ok'))

    def test_readiness_checks_the_database(self):
        self.assertEqual(self.client.get('/readyz').content, b'ready')
        with (
            mock.patch('core.views.connection.cursor', side_effect=OperationalError('down')),
            self.assertLogs('security', 'ERROR'),
        ):
            response = self.client.get('/readyz')
        self.assertEqual(response.status_code, 503)

    def test_probes_only_accept_get(self):
        self.assertEqual(self.client.post('/healthz').status_code, 405)


@override_settings(STAFF_MFA_REQUIRED=False)
class SecurityLogTests(TestCase):
    def test_failed_sign_in_is_logged_without_the_password(self):
        with self.assertLogs('security', 'WARNING') as logs:
            self.client.post(reverse('login'), {'username': 'staff', 'password': 'Secret-Value-123'})
        output = '\n'.join(logs.output)
        self.assertIn("auth.login_failed username='staff'", output)
        self.assertNotIn('Secret-Value-123', output)

    def test_sign_in_and_out_are_logged(self):
        User.objects.create_user('staff', 's@example.com', PASSWORD, is_staff=True)
        with self.assertLogs('security', 'INFO') as logs:
            self.client.post(reverse('login'), {'username': 'staff', 'password': PASSWORD})
            self.client.post(reverse('logout'))
        output = '\n'.join(logs.output)
        self.assertIn('auth.login', output)
        self.assertIn('auth.logout', output)
        self.assertNotIn(PASSWORD, output)


class CspReportTests(TestCase):
    def report(self, body):
        return self.client.post('/csp-report/', body, content_type='application/csp-report')

    def test_violation_is_logged(self):
        body = json.dumps({'csp-report': {'violated-directive': 'script-src', 'blocked-uri': 'https://evil.example'}})
        with self.assertLogs('security', 'WARNING') as logs:
            self.assertEqual(self.report(body).status_code, 204)
        self.assertIn('evil.example', logs.output[0])

    def test_oversized_or_invalid_reports_are_ignored(self):
        self.assertEqual(self.report('x' * 20_000).status_code, 204)
        self.assertEqual(self.report('not json').status_code, 204)


def failing_view(request):
    raise RuntimeError('boom')


# URLconf for ErrorPageTests: a view that always fails.
urlpatterns = [path('boom/', failing_view)]


class ErrorPageTests(SimpleTestCase):
    def test_404_page(self):
        response = self.client.get('/no-such-page/')
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, '404.html')
        self.assertContains(response, 'Page not found', status_code=404)

    @override_settings(ROOT_URLCONF='core.tests.test_operations')
    def test_500_page_shows_no_details(self):
        self.client.raise_request_exception = False
        with self.assertLogs('django.request', 'ERROR'):
            response = self.client.get('/boom/')
        self.assertEqual(response.status_code, 500)
        self.assertContains(response, 'Something went wrong', status_code=500)
        self.assertNotContains(response, 'boom', status_code=500)
        self.assertNotContains(response, 'Traceback', status_code=500)
