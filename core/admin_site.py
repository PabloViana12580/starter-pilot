from django.conf import settings
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .mfa import mfa_satisfied


class StaffAdminSite(admin.AdminSite):
    """The admin, for active staff who have also passed two-factor login when required."""

    site_header = settings.SITE_NAME
    site_title = settings.SITE_NAME
    index_title = _('Administration')

    def has_permission(self, request):
        return super().has_permission(request) and mfa_satisfied(request.user)
