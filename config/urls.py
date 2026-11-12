"""
URL configuration.

Business modules add their URLs through config.modules.MODULE_URLS. core
answers "/" only when no module does.
"""

from django.conf import settings
from django.contrib import admin
from django.templatetags.static import static
from django.urls import include, path
from django.views.generic import RedirectView

from config.modules import MODULE_URLS
from core import views

urlpatterns = [
    path('healthz', views.healthz, name='healthz'),
    path('readyz', views.readyz, name='readyz'),
    path('csp-report/', views.csp_report, name='csp_report'),
    # Browsers and bots ask for /favicon.ico even when pages link the SVG icon.
    path('favicon.ico', RedirectView.as_view(url=static('img/favicon.svg'), permanent=True)),
    path('accounts/', include('core.account_urls')),
    # Staff sign in on the site's own login page (with lockout and two-factor).
    path(f'{settings.ADMIN_URL}login/', RedirectView.as_view(pattern_name='login', query_string=True)),
    path(settings.ADMIN_URL, admin.site.urls),
    *[path(prefix, include(urlconf)) for prefix, urlconf in MODULE_URLS],
    path('', views.index, name='index'),
]
