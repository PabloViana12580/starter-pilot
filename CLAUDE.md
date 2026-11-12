# CLAUDE.md

Starter Pilot: A throwaway project that tests the django-starter skill. A Django website for a small business, created with the
django-starter skill 0.1.0 (`.starter.json` records the options). `README.md` is
for the business owner and stays non-technical; technical documentation is in `docs/DEVELOPER.md`.

Project rules (stack, security, secrets, frontend, code design) are in `AGENTS.md` and apply here:

@AGENTS.md

## Commands

Windows with Git Bash. The virtualenv is `.venv` (Python 3.13); call its interpreter directly.

```bash
.venv/Scripts/python.exe manage.py runserver                   # http://127.0.0.1:8000, needs .env
.venv/Scripts/python.exe manage.py check
.venv/Scripts/python.exe manage.py dbcheck                     # connection, TLS, isolation, row level security
.venv/Scripts/python.exe manage.py makemigrations --check --dry-run
.venv/Scripts/python.exe manage.py migrate
.venv/Scripts/python.exe manage.py test --noinput
.venv/Scripts/python.exe manage.py optimize_images             # src/images -> static/img (WebP) + credits
.venv/Scripts/python.exe manage.py createsuperuser
.venv/Scripts/python.exe manage.py reset_mfa <username>        # lost phone: re-enroll two-factor
.venv/Scripts/ruff.exe check . && .venv/Scripts/ruff.exe format --check .
```

Dependencies: edit `requirements.in` / `requirements-dev.in`, then
`.venv/Scripts/python.exe -m piptools compile --generate-hashes --allow-unsafe --strip-extras requirements.in`
(same for `requirements-dev.in`) and `pip install --require-hashes -r requirements.txt -r requirements-dev.txt`.

## Business modules in this project

| Module | Apps | What it does |
| --- | --- | --- |
| Website | `pages` | Public pages in the style of the reference site: home, about, privacy policy, and terms of use. Product and service pages appear here when Catalog is added. |
| CRM | `crm` | A tiny CRM: contacts with notes, tags, and a timeline; the website contact form creates leads and emails the owner; lead stages (new, contacted, quoted, won, lost); follow-up tasks with due dates; CSV export; marketing consent records; per-contact data export. Managed in the branded admin. Orders and appointments from later modules land on the same timeline. |

`config/modules.py` lists their apps and URLs. Modules not listed here can be added later from the
django-starter skill (copy the module's folder, then update `config/modules.py`, settings, and docs).

## Layout

| Path | Responsibility |
| --- | --- |
| `config/` | Settings (`database_from_env()`, security, site identity, email, logging), URLs, `platforms.py` (host names of hosting platforms), `modules.py`, `test_runner.py`. |
| `core/` | Sign-in with lockout and two-factor (`account_views.py`, `mfa.py`), staff admin site, middleware (absolute session timeout, two-factor gate, Permissions-Policy), probes and CSP reports (`views.py`), RLS after migrate (`rls.py`), spam protection and rate limits (`spam.py`), email (`notifications.py`), client address (`net.py`), security event logging (`signals.py`), commands `dbcheck`, `optimize_images`, `reset_mfa`, tests for the core features. |
| `templates/` | `base.html`, `components/`, sign-in pages, error pages (`error_base.html` is standalone), admin branding. |
| `static/` | `css/app.css` (tokens), `css/fonts.css`, `css/admin.css`, `js/app.js`, `vendor/bootstrap/`, `img/` (web images + `CREDITS.md`). |
| `src/images/` | The owner's original images (committed; not under the MIT license). |
| `docs/` | `DEVELOPER.md`, `security/CONTROLS.md`, `security/THREAT_MODEL.md`, `operations/RUNBOOK.md`. |

URLs: `/healthz`, `/readyz`, `/csp-report/`, `/accounts/login/`, `/accounts/logout/` (POST),
`/accounts/two-factor/setup/` and `verify/`, `/<DJANGO_ADMIN_URL>` (default `admin/`), plus the modules' URLs.

## Conventions and pitfalls

- **Database**: Supabase needs the Session pooler URI (port 5432); the direct `db.<ref>.supabase.co` host is IPv6-only and the transaction pooler (6543) is rejected by settings. Tests create `test_<dbname>` on the same server; if an interrupted run leaves it behind, drop it with `DROP DATABASE ... WITH (FORCE)`.
- **New table or module**: nothing to add for row level security (automatic), but run `manage.py dbcheck` and the tests.
- **CSP**: a page that looks unstyled or a button that does nothing usually means an inline style or script; check the browser console and the `csp.violation` log lines.
- **Two-factor**: on by default when a module stores personal data (`STAFF_MFA_REQUIRED`). Locally you can set `STAFF_MFA_REQUIRED=false` in `.env` while developing.
- **Rate limits** use the in-process cache: keep one gunicorn worker (threads are fine) or move the cache to a shared backend.
- **Client addresses** behind a proxy depend on `DJANGO_TRUSTED_PROXY_COUNT`; set it per hosting platform (docs/DEVELOPER.md).
- **Line endings**: `.gitattributes` keeps LF everywhere.
- **Placeholders**: `STARTER-TODO` marks text the project still has to replace (home, about, legal pages); none may remain at release.
