"""F3 authentication: sign-in, lockout, sign-out, admin access, password storage, sessions."""

import time

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from core.middleware import SESSION_STARTED_KEY

User = get_user_model()
PASSWORD = 'correct-Horse-battery-42'


@override_settings(STAFF_MFA_REQUIRED=False)
class LoginTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('staff', 'staff@example.com', PASSWORD, is_staff=True)
        self.url = reverse('login')

    def login(self, password=PASSWORD, **extra):
        return self.client.post(self.url, {'username': 'staff', 'password': password, **extra})

    def test_login_page_has_labelled_fields_and_csrf(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'csrfmiddlewaretoken')
        self.assertContains(response, 'autocomplete="username"')
        self.assertContains(response, 'autocomplete="current-password"')
        self.assertContains(response, '<label class="field__label" for="id_username">', html=False)

    def test_successful_login_goes_to_admin(self):
        response = self.login()
        self.assertRedirects(response, reverse('admin:index'))
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)

    def test_wrong_password_gives_one_generic_message(self):
        wrong_password = self.login(password='wrong')
        unknown_user = self.client.post(self.url, {'username': 'nobody', 'password': 'wrong'})
        for response in (wrong_password, unknown_user):
            self.assertContains(response, 'Please enter a correct username and password')
            self.assertContains(response, 'role="alert"')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_lockout_after_repeated_failures(self):
        for _attempt in range(5):
            self.login(password='wrong')
        response = self.login()  # even the right password is refused now
        self.assertEqual(response.status_code, 429)
        self.assertTemplateUsed(response, 'registration/locked_out.html')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_inactive_user_cannot_log_in(self):
        self.user.is_active = False
        self.user.save()
        self.login()
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_external_next_url_is_ignored(self):
        response = self.login(next='https://evil.example.com/')
        self.assertRedirects(response, reverse('admin:index'))

    def test_account_without_staff_access_goes_home_not_into_a_loop(self):
        User.objects.create_user('member', 'm@example.com', PASSWORD)
        response = self.client.post(self.url, {'username': 'member', 'password': PASSWORD})
        self.assertRedirects(response, '/', fetch_redirect_response=False)
        admin = self.client.get(reverse('admin:index'), follow=True)
        self.assertTemplateUsed(admin, 'registration/login.html')


@override_settings(STAFF_MFA_REQUIRED=False)
class LogoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('staff', 'staff@example.com', PASSWORD, is_staff=True)
        self.client.force_login(self.user)

    def test_post_logout_ends_session(self):
        self.client.post(reverse('logout'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_get_logout_is_rejected(self):
        self.assertEqual(self.client.get(reverse('logout')).status_code, 405)
        self.assertIn('_auth_user_id', self.client.session)

    def test_logout_tells_the_browser_to_clear_site_data(self):
        response = self.client.post(reverse('logout'))
        self.assertEqual(response['Clear-Site-Data'], '"cache", "cookies", "storage"')

    def test_disabling_an_account_ends_its_sessions(self):
        self.assertEqual(self.client.get(reverse('admin:index')).status_code, 200)
        self.user.is_active = False
        self.user.save()
        self.assertNotEqual(self.client.get(reverse('admin:index')).status_code, 200)

    def test_logout_requires_csrf_token(self):
        client = self.client_class(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(reverse('logout')).status_code, 403)


@override_settings(STAFF_MFA_REQUIRED=False)
class AdminAccessTests(TestCase):
    def test_regular_account_cannot_open_admin(self):
        self.client.force_login(User.objects.create_user('member', 'm@example.com', PASSWORD))
        response = self.client.get(reverse('admin:index'))
        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(response['Location'], reverse('admin:index'))

    def test_staff_can_open_admin(self):
        self.client.force_login(User.objects.create_user('staff', 's@example.com', PASSWORD, is_staff=True))
        self.assertEqual(self.client.get(reverse('admin:index')).status_code, 200)

    def test_admin_names_security_sections_in_plain_words(self):
        self.client.force_login(User.objects.create_superuser('owner', 'o@example.com', PASSWORD))
        response = self.client.get(reverse('admin:index'))
        self.assertContains(response, 'Sign-in security')
        self.assertContains(response, 'Two-factor sign-in')
        self.assertNotContains(response, 'Otp_Totp')

    def test_admin_login_page_is_the_sites_login(self):
        response = self.client.get(f'{reverse("admin:index")}login/?next=/x/')
        self.assertRedirects(response, f'{reverse("login")}?next=/x/', fetch_redirect_response=False)


class PasswordStorageTests(TestCase):
    def test_new_passwords_use_argon2id(self):
        user = User.objects.create_user('staff', 's@example.com', PASSWORD)
        self.assertTrue(user.password.startswith('argon2$argon2id$'))

    def test_weak_passwords_are_rejected(self):
        for weak in ('password', 'short-1A', '1234567890123'):
            with self.subTest(password=weak), self.assertRaises(ValidationError):
                validate_password(weak)
        validate_password(PASSWORD)


@override_settings(STAFF_MFA_REQUIRED=False, SESSION_ABSOLUTE_TIMEOUT_SECONDS=3600)
class SessionLifetimeTests(TestCase):
    def test_session_ends_after_absolute_timeout_even_when_active(self):
        self.client.force_login(User.objects.create_user('staff', 's@example.com', PASSWORD, is_staff=True))
        self.assertEqual(self.client.get(reverse('admin:index')).status_code, 200)
        session = self.client.session
        session[SESSION_STARTED_KEY] = int(time.time()) - 3601
        session.save()
        response = self.client.get(reverse('admin:index'))
        self.assertTrue(response['Location'].startswith(reverse('login')))
        self.assertNotIn('_auth_user_id', self.client.session)
