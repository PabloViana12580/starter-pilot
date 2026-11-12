"""Spam protection helpers and client address handling used by public forms and lockout."""

import time
from unittest import mock

from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, override_settings

from core.net import client_ip
from core.spam import SpamProtectedForm, rate_limited


class ClientIpTests(SimpleTestCase):
    def request(self, forwarded=''):
        return RequestFactory().get('/', REMOTE_ADDR='10.0.0.1', HTTP_X_FORWARDED_FOR=forwarded)

    @override_settings(TRUSTED_PROXY_COUNT=0)
    def test_without_proxies_forwarded_header_is_ignored(self):
        self.assertEqual(client_ip(self.request('6.6.6.6')), '10.0.0.1')

    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_one_proxy_uses_the_address_it_appended(self):
        # A client can prepend fake entries; only the proxy's own entry is trusted.
        self.assertEqual(client_ip(self.request('6.6.6.6, 203.0.113.9')), '203.0.113.9')


class RateLimitTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_blocks_after_the_limit_within_the_window(self):
        request = RequestFactory().get('/', REMOTE_ADDR='10.0.0.2')
        results = [rate_limited(request, 'test', limit=3, window=60) for _attempt in range(4)]
        self.assertEqual(results, [False, False, False, True])


class SpamProtectedFormTests(SimpleTestCase):
    def submission(self, **overrides):
        started = SpamProtectedForm().initial['started']
        return {'website': '', 'started': started, **overrides}

    def test_normal_submission_passes(self):
        data = self.submission()
        with mock.patch('core.spam.time.time', return_value=time.time() + 10):
            form = SpamProtectedForm(data)
            self.assertTrue(form.is_valid())
            self.assertEqual(form.spam_reason(), '')

    def test_honeypot_too_fast_and_tampered_timestamps_are_caught(self):
        cases = {
            'honeypot': self.submission(website='http://spam.example'),
            'too_fast': self.submission(),
            'bad_timestamp': self.submission(started='12345:forged'),
        }
        for reason, data in cases.items():
            with self.subTest(reason=reason):
                form = SpamProtectedForm(data)
                form.is_valid()
                self.assertEqual(form.spam_reason(), reason)
