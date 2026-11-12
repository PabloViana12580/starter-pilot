"""F1 configuration and F2 database settings (no database connection needed)."""

import json
import os
import subprocess
import sys
from unittest import mock

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from config.platforms import platform_hostnames
from config.settings import database_from_env

PRODUCTION_ENV = {
    'DJANGO_DEBUG': 'false',
    'DJANGO_SECRET_KEY': 'test-only-' + 'x' * 60,
    'DJANGO_ALLOWED_HOSTS': 'shop.example.com',
    'DATABASE_URL': 'postgresql://u:p@db.example.com:5432/app',
}


def run_in_fresh_process(code, env, *args):
    """Import settings (or run manage.py) in a new interpreter with exactly `env`."""
    full_env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(('DJANGO_', 'DATABASE_URL', 'DB_', 'RENDER_', 'RAILWAY_', 'FLY_', 'WEBSITE_'))
    }
    full_env.update(
        {
            'DJANGO_SETTINGS_MODULE': 'config.settings',
            'PYTHONPATH': str(settings.BASE_DIR),
            # Skip the developer's .env, so only `env` configures the process.
            'DJANGO_ENV_FILE': str(settings.BASE_DIR / '.env.not-used-in-tests'),
            **env,
        }
    )
    command = [sys.executable, *args] if args else [sys.executable, '-c', code]
    return subprocess.run(command, env=full_env, cwd=settings.BASE_DIR, capture_output=True, text=True)


class DatabaseConfigTests(SimpleTestCase):
    def config(self, **env):
        with mock.patch.dict(os.environ, env, clear=True):
            return database_from_env()

    def test_parses_database_url_with_encoded_password(self):
        db = self.config(DATABASE_URL='postgresql://postgres.ref:p%40ss%2Fword@pooler.example.com:5432/postgres')
        self.assertEqual(db['ENGINE'], 'django.db.backends.postgresql')
        self.assertEqual((db['USER'], db['PASSWORD']), ('postgres.ref', 'p@ss/word'))
        self.assertEqual((db['HOST'], db['PORT'], db['NAME']), ('pooler.example.com', '5432', 'postgres'))

    def test_tls_required_by_default(self):
        db = self.config(DATABASE_URL='postgresql://u:p@db.example.com:5432/app')
        self.assertEqual(db['OPTIONS'], {'sslmode': 'require'})

    def test_url_query_parameters_are_passed_to_the_driver(self):
        url = 'postgresql://u:p@ep-x.neon.tech/app?sslmode=require&channel_binding=require&connect_timeout=10'
        db = self.config(DATABASE_URL=url)
        self.assertEqual(db['OPTIONS'], {'sslmode': 'require', 'channel_binding': 'require', 'connect_timeout': '10'})

    def test_weak_tls_modes_only_for_local_servers(self):
        local = self.config(DATABASE_URL='postgresql://u:p@localhost/app?sslmode=disable')
        self.assertEqual(local['OPTIONS']['sslmode'], 'disable')
        with self.assertRaises(ImproperlyConfigured):
            self.config(DATABASE_URL='postgresql://u:p@db.example.com/app?sslmode=disable')
        with self.assertRaises(ImproperlyConfigured):
            self.config(DATABASE_URL='postgresql://u:p@db.example.com/app', DB_SSLMODE='prefer')

    def test_stricter_tls_and_root_certificate(self):
        db = self.config(DATABASE_URL='postgresql://u:p@h.example.com/app', DB_SSLMODE='verify-full', DB_SSLROOTCERT='/ca.crt')
        self.assertEqual(db['OPTIONS'], {'sslmode': 'verify-full', 'sslrootcert': '/ca.crt'})

    def test_individual_variables(self):
        db = self.config(DB_HOST='localhost', DB_USER='u', DB_PASSWORD='p', DB_NAME='app', DB_SSLMODE='disable')
        self.assertEqual((db['HOST'], db['NAME'], db['PORT']), ('localhost', 'app', '5432'))

    def test_missing_configuration_names_the_variables(self):
        with self.assertRaisesMessage(ImproperlyConfigured, 'DB_HOST, DB_USER, DB_PASSWORD'):
            self.config()

    def test_rejects_non_postgres_and_incomplete_urls(self):
        for url in ('sqlite:///db.sqlite3', 'mysql://u:p@h/app', 'postgresql://h.example.com/app'):
            with self.subTest(url=url), self.assertRaises(ImproperlyConfigured):
                self.config(DATABASE_URL=url)

    def test_rejects_supabase_transaction_pooler(self):
        with self.assertRaisesMessage(ImproperlyConfigured, 'Session pooler'):
            self.config(DATABASE_URL='postgresql://u:p@aws-0-eu-central-1.pooler.supabase.com:6543/postgres')


class PlatformHostTests(SimpleTestCase):
    def test_known_platform_variables_become_host_names(self):
        self.assertEqual(platform_hostnames({'RENDER_EXTERNAL_HOSTNAME': 'app.onrender.com'}), ['app.onrender.com'])
        self.assertEqual(platform_hostnames({'FLY_APP_NAME': 'shop'}), ['shop.fly.dev'])
        self.assertEqual(platform_hostnames({}), [])


class ProductionSettingsTests(SimpleTestCase):
    """Settings as a production server imports them: DEBUG off, real secret key."""

    def load(self, **env):
        script = (
            'import json; from django.conf import settings as s; '
            'print(json.dumps([s.DEBUG, s.ALLOWED_HOSTS, s.CSRF_TRUSTED_ORIGINS, s.SESSION_COOKIE_SECURE, '
            's.CSRF_COOKIE_SECURE, s.SECURE_SSL_REDIRECT, s.SECURE_HSTS_SECONDS, list(s.SECURE_PROXY_SSL_HEADER), '
            's.SESSION_COOKIE_NAME, s.CSRF_COOKIE_NAME]))'
        )
        result = run_in_fresh_process(script, {**PRODUCTION_ENV, **env})
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_secure_defaults_with_debug_off(self):
        debug, hosts, _origins, session_secure, csrf_secure, ssl_redirect, hsts, proxy, *cookie_names = self.load()
        self.assertFalse(debug)
        self.assertEqual(hosts, ['shop.example.com'])
        self.assertTrue(session_secure and csrf_secure and ssl_redirect)
        self.assertGreaterEqual(hsts, 31536000)
        self.assertEqual(proxy, ['HTTP_X_FORWARDED_PROTO', 'https'])
        self.assertEqual(cookie_names, ['__Host-sessionid', '__Host-csrftoken'])

    def test_platform_host_is_trusted_without_configuration(self):
        _debug, hosts, origins, *_ = self.load(RAILWAY_PUBLIC_DOMAIN='shop.up.railway.app')
        self.assertIn('shop.up.railway.app', hosts)
        self.assertIn('https://shop.up.railway.app', origins)

    def test_secret_key_is_required_with_debug_off(self):
        env = {**PRODUCTION_ENV, 'DJANGO_SECRET_KEY': ''}
        result = run_in_fresh_process('from django.conf import settings; settings.SECRET_KEY', env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('DJANGO_SECRET_KEY', result.stderr)

    def test_deployment_checklist_passes(self):
        manage = str(settings.BASE_DIR / 'manage.py')
        result = run_in_fresh_process('', PRODUCTION_ENV, manage, 'check', '--deploy', '--fail-level', 'WARNING')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
