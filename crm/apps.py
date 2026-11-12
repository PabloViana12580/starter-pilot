from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CrmConfig(AppConfig):
    name = 'crm'
    verbose_name = _('Customers (CRM)')
