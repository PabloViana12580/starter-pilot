"""App configs that adapt framework and third-party apps to this site (installed in settings)."""

from axes.apps import AppConfig as AxesConfig
from django.contrib.admin.apps import AdminConfig
from django.utils.translation import gettext_lazy as _
from django_otp.plugins.otp_totp.apps import DefaultConfig as TOTPConfig


class StaffAdminConfig(AdminConfig):
    """django.contrib.admin, using the admin site that also requires two-factor login."""

    default_site = 'core.admin_site.StaffAdminSite'


class SignInSecurityConfig(AxesConfig):
    """django-axes (login lockout) under a name staff understand in the admin."""

    verbose_name = _('Sign-in security')


class TwoFactorConfig(TOTPConfig):
    """django-otp authenticator apps (TOTP) under a name staff understand in the admin."""

    verbose_name = _('Two-factor sign-in')
