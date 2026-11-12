"""F6 site shell: identity, accessibility basics, and static files that exist."""

import re
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.contrib.staticfiles import finders
from django.test import SimpleTestCase, TestCase, override_settings

STATIC_TAG = re.compile(r"""{%\s*static\s+['"]([^'"]+)['"]\s*%}""")


class SiteShellTests(TestCase):
    def test_home_shows_site_identity_with_language_and_skip_link(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, settings.SITE_NAME)
        self.assertContains(response, f'<html lang="{settings.LANGUAGE_CODE}">')
        self.assertContains(response, 'href="#main"')
        self.assertContains(response, 'id="main"')

    @override_settings(SITE_PHONE='+1 (860) 555-0100')
    def test_phone_link_uses_digits_only(self):
        self.assertContains(self.client.get('/'), 'href="tel:+18605550100"')

    def test_favicon_ico_points_to_the_site_icon(self):
        response = self.client.get('/favicon.ico')
        self.assertRedirects(response, '/static/img/favicon.svg', status_code=301, fetch_redirect_response=False)

    def test_footer_offers_staff_sign_in(self):
        self.assertContains(self.client.get('/'), 'href="/accounts/login/"')

    def test_sign_in_page_shows_the_site_name(self):
        # Django's LoginView puts its own `site` in the context; ours is `site_info`.
        self.assertContains(self.client.get('/accounts/login/'), f'<span class="brand__name">{settings.SITE_NAME}</span>')

    @override_settings(LANGUAGE_CODE='es')
    def test_interface_is_translated_for_spanish_sites(self):
        response = self.client.get('/accounts/login/')
        self.assertContains(response, '<html lang="es">')
        self.assertContains(response, 'Iniciar sesión')
        self.assertContains(response, 'Saltar al contenido')


class StaticFileReferenceTests(SimpleTestCase):
    def template_dirs(self):
        yield from (Path(directory) for directory in settings.TEMPLATES[0]['DIRS'])
        for app in apps.get_app_configs():
            path = Path(app.path) / 'templates'
            if path.is_dir() and str(settings.BASE_DIR) in str(path):
                yield path

    def test_every_static_file_referenced_by_a_template_exists(self):
        missing = []
        for directory in self.template_dirs():
            for template in directory.rglob('*.html'):
                for reference in STATIC_TAG.findall(template.read_text(encoding='utf-8')):
                    if not finders.find(reference):
                        missing.append(f'{template.name}: {reference}')
        self.assertEqual(missing, [])
