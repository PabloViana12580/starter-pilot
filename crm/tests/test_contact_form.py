"""The website contact form: leads, spam protection, rate limit, CSRF."""

import time
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from core.spam import SpamProtectedForm
from crm.models import Contact


@override_settings(CRM_CONTACT_RATE_LIMIT=3)
class ContactFormTests(TestCase):
    def setUp(self):
        cache.clear()
        self.url = reverse('crm:contact')

    def form_data(self, **overrides):
        data = {
            'name': 'Ana Ruiz',
            'email': 'ana@example.com',
            'phone': '',
            'message': 'Hello',
            'website': '',
            'started': SpamProtectedForm().initial['started'],
        }
        return {**data, **overrides}

    def post(self, data, delay=10):
        with mock.patch('core.spam.time.time', return_value=time.time() + delay):
            return self.client.post(self.url, data)

    def test_page_has_the_form_with_a_hidden_honeypot(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'autocomplete="email"')
        self.assertContains(response, 'class="field field--trap" aria-hidden="true"')
        self.assertContains(response, 'name="started"')

    def test_valid_message_creates_a_lead(self):
        response = self.post(self.form_data(marketing_consent='on'))
        self.assertRedirects(response, reverse('crm:contact_thanks'))
        contact = Contact.objects.get(email='ana@example.com')
        self.assertTrue(contact.marketing_consent)
        self.assertEqual(contact.interactions.count(), 1)

    def test_invalid_input_shows_errors(self):
        response = self.post(self.form_data(email='not-an-email', message=''))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'role="alert"')
        self.assertFalse(Contact.objects.exists())

    def test_bots_see_success_but_nothing_is_saved(self):
        for data, delay in ((self.form_data(website='http://spam.example'), 10), (self.form_data(), 0)):
            with self.subTest(data=data['website'], delay=delay), self.assertLogs('security', 'WARNING'):
                response = self.post(data, delay=delay)
                self.assertRedirects(response, reverse('crm:contact_thanks'))
        self.assertFalse(Contact.objects.exists())

    def test_rate_limit_per_address(self):
        for index in range(3):
            self.post(self.form_data(email=f'p{index}@example.com'))
        with self.assertLogs('security', 'WARNING'):
            response = self.post(self.form_data(email='p9@example.com'))
        self.assertEqual(response.status_code, 429)
        self.assertEqual(Contact.objects.count(), 3)

    def test_csrf_token_is_required(self):
        client = self.client_class(enforce_csrf_checks=True)
        self.assertEqual(client.post(self.url, self.form_data()).status_code, 403)
