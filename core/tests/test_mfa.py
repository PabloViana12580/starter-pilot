"""F3 two-factor sign-in for staff (TOTP authenticator apps)."""

import re
from io import StringIO
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice

User = get_user_model()
PASSWORD = 'correct-Horse-battery-42'


def current_code(device):
    return f'{totp(device.bin_key, step=device.step, t0=device.t0, digits=device.digits):0{device.digits}d}'


@override_settings(STAFF_MFA_REQUIRED=True)
class EnrollmentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('staff', 'staff@example.com', PASSWORD, is_staff=True)

    def sign_in(self):
        return self.client.post(reverse('login'), {'username': 'staff', 'password': PASSWORD})

    def test_first_sign_in_leads_to_setup_with_a_qr_code(self):
        response = self.sign_in()
        self.assertTrue(response['Location'].startswith(reverse('mfa_setup')))
        page = self.client.get(response['Location'])
        self.assertContains(page, '<svg')
        self.assertContains(page, 'autocomplete="one-time-code"')

    def test_valid_code_turns_on_two_factor_and_lets_staff_in(self):
        self.sign_in()
        self.client.get(reverse('mfa_setup'))
        device = TOTPDevice.objects.get(user=self.user)
        response = self.client.post(reverse('mfa_setup'), {'token': current_code(device)})
        self.assertRedirects(response, reverse('admin:index'))
        device.refresh_from_db()
        self.assertTrue(device.confirmed)
        self.assertEqual(self.client.get(reverse('admin:index')).status_code, 200)

    def test_wrong_code_does_not_confirm(self):
        self.sign_in()
        self.client.get(reverse('mfa_setup'))
        response = self.client.post(reverse('mfa_setup'), {'token': '000000'})
        self.assertContains(response, 'That code is not valid')
        self.assertFalse(TOTPDevice.objects.get(user=self.user).confirmed)

    def test_unverified_staff_are_held_at_the_two_factor_step(self):
        self.sign_in()
        for path in (reverse('admin:index'), '/'):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertTrue(response['Location'].startswith(reverse('mfa_setup')))
        self.assertEqual(self.client.post(reverse('logout')).status_code, 302)


@override_settings(STAFF_MFA_REQUIRED=True)
class VerificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('staff', 'staff@example.com', PASSWORD, is_staff=True)
        self.device = TOTPDevice.objects.create(user=self.user, name='phone', confirmed=True)
        response = self.client.post(reverse('login'), {'username': 'staff', 'password': PASSWORD, 'next': '/x/'})
        self.verify_url = response['Location']

    def test_sign_in_asks_for_the_code_and_keeps_next(self):
        self.assertEqual(self.verify_url, f'{reverse("mfa_verify")}?{urlencode({"next": "/x/"})}')
        self.assertEqual(self.client.get(reverse('admin:index'))['Location'].split('?')[0], reverse('mfa_verify'))

    def test_current_code_lets_staff_in(self):
        response = self.client.post(self.verify_url, {'token': current_code(self.device), 'next': reverse('admin:index')})
        self.assertRedirects(response, reverse('admin:index'))

    def test_a_code_cannot_be_reused(self):
        code = current_code(self.device)
        self.client.post(self.verify_url, {'token': code})
        self.assertEqual(self.client.get(reverse('admin:index')).status_code, 200)
        self.client.post(reverse('logout'))
        self.client.post(reverse('login'), {'username': 'staff', 'password': PASSWORD})
        response = self.client.post(reverse('mfa_verify'), {'token': code})
        self.assertContains(response, 'That code is not valid')

    def test_reset_command_removes_devices_for_re_enrollment(self):
        out = StringIO()
        with self.assertLogs('security', 'WARNING'):
            call_command('reset_mfa', 'staff', stdout=out)
        self.assertIn('Removed 1 device(s)', out.getvalue())
        self.assertFalse(TOTPDevice.objects.filter(user=self.user).exists())

    def test_repeated_wrong_codes_sign_the_session_out(self):
        for _attempt in range(5):
            response = self.client.post(self.verify_url, {'token': '000000'})
        self.assertRedirects(response, reverse('login'), fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_setup_cannot_add_a_second_device_without_the_first(self):
        response = self.client.get(reverse('mfa_setup'))
        self.assertTrue(response['Location'].startswith(reverse('mfa_verify')))
        self.assertEqual(TOTPDevice.objects.filter(user=self.user).count(), 1)


class MfaSettingTests(TestCase):
    @override_settings(STAFF_MFA_REQUIRED=False)
    def test_staff_go_straight_in_when_two_factor_is_off(self):
        User.objects.create_user('staff', 's@example.com', PASSWORD, is_staff=True)
        response = self.client.post(reverse('login'), {'username': 'staff', 'password': PASSWORD})
        self.assertRedirects(response, reverse('admin:index'))

    def test_default_follows_the_modules_holding_personal_data(self):
        from django.conf import settings

        from config.modules import MODULES_HOLD_PERSONAL_DATA

        self.assertEqual(settings.STAFF_MFA_REQUIRED, MODULES_HOLD_PERSONAL_DATA)

    def test_qr_code_is_inline_svg_without_scripts(self):
        from core.mfa import qr_svg

        svg = qr_svg('otpauth://totp/Example:staff?secret=JBSWY3DPEHPK3PXP')
        self.assertTrue(svg.startswith('<svg'))
        self.assertIsNone(re.search(r'<script|style=', svg))
