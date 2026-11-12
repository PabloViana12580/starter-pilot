# Developer guide

## Architecture

Django 5.2 LTS, server-rendered templates with Bootstrap 5.3 (self-hosted), PostgreSQL (any
provider). The `core` app holds everything shared: configuration helpers, staff sign-in with
lockout and two-factor login, the admin site, security middleware, health and readiness probes,
spam protection, email, logging, and the design system. Business modules (listed in
`config/modules.py`) add the site's features:

| Module | Apps | What it does |
| --- | --- | --- |
| Website | `pages` | Public pages in the style of the reference site: home, about, privacy policy, and terms of use. Product and service pages appear here when Catalog is added. |
| CRM | `crm` | A tiny CRM: contacts with notes, tags, and a timeline; the website contact form creates leads and emails the owner; lead stages (new, contacted, quoted, won, lost); follow-up tasks with due dates; CSV export; marketing consent records; per-contact data export. Managed in the branded admin. Orders and appointments from later modules land on the same timeline. |

## Local setup

Requirements: Python 3.13, Git, and a PostgreSQL database (a cloud project or a local server).

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install --require-hashes -r requirements.txt -r requirements-dev.txt
cp .env.example .env            # then fill in DATABASE_URL and the SITE_* values
.venv/Scripts/python.exe manage.py dbcheck --before-migrate
.venv/Scripts/python.exe manage.py migrate
.venv/Scripts/python.exe manage.py createsuperuser
.venv/Scripts/python.exe manage.py runserver
```

On macOS/Linux use `.venv/bin/python`. The first time a staff account signs in, it sets up an
authenticator app (two-factor sign-in) when `STAFF_MFA_REQUIRED` is on.

### Database connection strings

| Provider | Where to find it | Notes |
| --- | --- | --- |
| Supabase | Dashboard > Connect > **Session pooler** > URI | Port 5432, user `postgres.<project-ref>`. Not the direct host (IPv6-only) nor the transaction pooler (6543). Free projects pause after a week without activity. |
| Neon | Dashboard > Connect | Keep `sslmode=require&channel_binding=require`; use the direct (non-pooled) host. |
| Aiven, Render, others | The service's connection URI | Add `?sslmode=require` if it isn't there. |
| Local PostgreSQL | `postgresql://user:password@localhost:5432/dbname?sslmode=disable` | Weak TLS modes are accepted only for localhost. |

URL-encode special characters in the password (`@` > `%40`, `/` > `%2F`, `#` > `%23`).
`manage.py dbcheck` confirms the connection, TLS, test-database privilege, that the database
holds no other project's tables, and (after `migrate`) that every table has row level security.

## Environment variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | Yes unless `DJANGO_DEBUG=true` | Signing key. Long and random; different per environment. |
| `DJANGO_DEBUG` | No | `true` for local development only. Off means secure cookies, HTTPS redirect, HSTS. |
| `DJANGO_ALLOWED_HOSTS` | Production | Comma-separated host names (platforms in `config/platforms.py` are added automatically). |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Custom domains | Comma-separated `https://` origins. |
| `DJANGO_TRUSTED_PROXY_COUNT` | Behind a proxy | Proxies that append to `X-Forwarded-For` (usually 1 on a platform). Wrong values let clients spoof addresses for lockout and rate limits. |
| `DJANGO_SECURE_PROXY_SSL_HEADER` | No | Default `HTTP_X_FORWARDED_PROTO,https`; `off` when no proxy terminates TLS. |
| `DJANGO_SECURE_SSL_REDIRECT` | No | Override the HTTPS redirect (default: on when debug is off). |
| `DJANGO_HSTS_SECONDS`, `DJANGO_HSTS_INCLUDE_SUBDOMAINS` | No | HSTS policy (default 1 year, subdomains included). |
| `DJANGO_ADMIN_URL` | No | Path of the administration (default `admin/`). |
| `DJANGO_TIME_ZONE`, `DJANGO_LANGUAGE_CODE` | No | Business time zone and site language (defaults chosen at project creation). |
| `DJANGO_ENV_FILE` | No | Read this file instead of `.env` (tests use it). |
| `DATABASE_URL` | Yes (or `DB_*`) | PostgreSQL URI; query parameters go to the driver. |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Alternative | Individual connection settings. |
| `DB_SSLMODE`, `DB_SSLROOTCERT` | No | TLS mode (default `require`) and CA file, or `system` for the OS trust store. |
| `DB_CONN_MAX_AGE` | No | Seconds to reuse connections (default 60). |
| `SITE_NAME`, `SITE_TAGLINE`, `SITE_URL`, `SITE_EMAIL`, `SITE_PHONE`, `SITE_ADDRESS`, `SITE_HOURS` | `SITE_URL` in production | Site identity and contact details shown on every page; `SITE_URL` is used in email links. |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL` | To send email | SMTP settings. Without `EMAIL_HOST`, emails are printed to the log. |
| `STAFF_MFA_REQUIRED` | No | Two-factor sign-in for staff (default on when a module stores personal data). |
| `PASSWORD_MIN_LENGTH` | No | Default 12. |
| `LOGIN_FAILURE_LIMIT`, `LOGIN_LOCKOUT_MINUTES` | No | Lockout after this many wrong passwords (default 5) for this long (default 15). |
| `SESSION_IDLE_TIMEOUT_MINUTES`, `SESSION_ABSOLUTE_TIMEOUT_HOURS` | No | Default 30 minutes idle, 12 hours maximum. |
| `LOG_LEVEL` | No | Default `INFO`. |

Modules add their own variables to `.env.example` (see the "Business modules" section there).

## Tests

```bash
.venv/Scripts/python.exe manage.py test --noinput
.venv/Scripts/coverage.exe run manage.py test --noinput && .venv/Scripts/coverage.exe report
```

Tests cover the starter's core features and each module's core features. They need a PostgreSQL
role that can create databases: Django creates `test_<dbname>` on the configured server and drops
it afterwards (`config/test_runner.py` uses `WITH (FORCE)` because poolers keep a connection open).
If the role can't create databases, run the tests against a local PostgreSQL instead.

CI (`.github/workflows/ci.yml`) runs on every push: ruff lint and format, migrations check,
`check --deploy` with production settings, tests with coverage (minimum in `pyproject.toml`) on a
PostgreSQL 17 container, bandit, pip-audit, a CycloneDX SBOM artifact, and a gitleaks secret scan.

## Deploying

Any platform that runs Python or containers works; deployment is a separate step per project.

- Build: `pip install --require-hashes -r requirements.txt && python manage.py collectstatic --noinput`
  (or the `Dockerfile`).
- Start: `gunicorn config.wsgi:application -c gunicorn.conf.py` (also in `Procfile`). Keep one
  worker with threads (`WEB_CONCURRENCY=1`, `GUNICORN_THREADS=4`) so the in-memory rate limits stay accurate.
- Release step: `python manage.py migrate` (run before or right after the new version starts).
- Health checks: liveness `/healthz` (no database), readiness `/readyz` (database). Both answer over HTTP.
- Environment: `DJANGO_SECRET_KEY`, `DATABASE_URL`, `SITE_URL`, `SITE_*`, email settings,
  `DJANGO_TRUSTED_PROXY_COUNT`, and `DJANGO_ALLOWED_HOSTS` / `DJANGO_CSRF_TRUSTED_ORIGINS` unless
  the platform is in `config/platforms.py`. Never set `DJANGO_DEBUG` in production.
- After the first deploy: create the owner's account (`createsuperuser`), sign in, set up two-factor.

`docs/operations/RUNBOOK.md` covers backups, incidents, and rotating secrets.

## Images and fonts

Put the owner's originals in `src/images/` and run `manage.py optimize_images`: WebP copies (max
2000 px wide, orientation fixed, metadata removed) go to `static/img/` and are listed in
`static/img/CREDITS.md`. Fonts are self-hosted: `.woff2` files and their license in
`static/fonts/`, `@font-face` rules in `static/css/fonts.css`, and the `--font-*` tokens in
`static/css/app.css`.

## Translations

The site has one language (`LANGUAGE_CODE`). Shared interface strings use Django's translation
functions; Django's own messages are already translated. Page content is written directly in
the site's language.

## Dependencies

Runtime packages are listed in `requirements.in` and pinned with hashes in `requirements.txt`
(pip-tools); development tools likewise in `requirements-dev.in` / `requirements-dev.txt`. After
editing an `.in` file, recompile it (command in CLAUDE.md) and commit both files. Dependabot opens
weekly update pull requests; CI must pass before merging.
