"""F4 browser protections: security headers and HTTPS redirect."""

from django.test import TestCase, override_settings


class SecurityHeaderTests(TestCase):
    def setUp(self):
        self.response = self.client.get('/')

    def test_content_security_policy_allows_only_this_site(self):
        policy = self.response['Content-Security-Policy']
        self.assertIn("default-src 'self'", policy)
        self.assertIn("script-src 'self'", policy)
        self.assertIn("frame-ancestors 'none'", policy)
        self.assertIn("object-src 'none'", policy)
        self.assertNotIn('unsafe-inline', policy)
        self.assertNotIn('unsafe-eval', policy)

    def test_other_protective_headers(self):
        self.assertEqual(self.response['X-Frame-Options'], 'DENY')
        self.assertEqual(self.response['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(self.response['Referrer-Policy'], 'same-origin')
        self.assertEqual(self.response['Cross-Origin-Opener-Policy'], 'same-origin')
        self.assertIn('camera=()', self.response['Permissions-Policy'])

    def test_pages_include_no_inline_scripts_or_styles(self):
        html = self.response.content.decode()
        self.assertNotRegex(html, r'<script(?![^>]*\bsrc=)[^>]*>')
        self.assertNotIn('style="', html)


# Class level, so the middleware chain is built with these values (SecurityMiddleware reads them once).
@override_settings(SECURE_HSTS_SECONDS=31536000, SECURE_HSTS_INCLUDE_SUBDOMAINS=True)
class StrictTransportSecurityTests(TestCase):
    def test_hsts_on_https(self):
        response = self.client.get('/', secure=True)
        self.assertEqual(response['Strict-Transport-Security'], 'max-age=31536000; includeSubDomains')


@override_settings(SECURE_SSL_REDIRECT=True)
class HttpsRedirectTests(TestCase):
    def test_plain_http_is_redirected(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 301)
        self.assertTrue(response['Location'].startswith('https://'))

    def test_health_checks_answer_over_http(self):
        self.assertEqual(self.client.get('/healthz').status_code, 200)
        self.assertEqual(self.client.get('/readyz').status_code, 200)
