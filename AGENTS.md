# AGENTS.md

Rules for anyone (human or AI agent) changing this repository.

## Stack and ownership

- Backend: Python 3.13 and Django 5.2 LTS (`config/` is the project package).
- Frontend: Django templates, Bootstrap 5.3 (self-hosted in `static/vendor/`), custom CSS (`static/css/app.css`), and minimal vanilla JavaScript (`static/js/app.js`). No React, no separate frontend app, no CDN.
- Authentication: Django's built-in auth for staff, with django-axes (lockout) and django-otp (two-factor). No public sign-up yet.
- Database: PostgreSQL only, any provider (Supabase, Neon, Aiven, Render, local). Django connects directly with database credentials; provider client SDKs and API keys are not part of the data path.
- Apps: `core` (cross-cutting: security, sign-in, probes, logging helpers, spam protection, email, design system) and business modules listed in `config/modules.py` (see CLAUDE.md). Each module owns its models and depends only on `core` and the modules it declares.
- Change application schema only through Django models and migrations. Never create or alter app tables by hand in SQL or a database dashboard.
- Never drop, truncate, or reset database objects you did not create for the task. Confirm which database `.env` points to before running `migrate` or writing data.
- Every table in the `public` schema has row level security: `core/rls.py` enables it after every `migrate`, and `core/tests/test_database.py` plus `manage.py dbcheck` verify it.

## Security (OWASP ASVS 5.0 level 1 + selected level 2; see docs/security/CONTROLS.md)

- Keep every control in `docs/security/CONTROLS.md` working, and update that file when you add, change, or remove a control.
- No inline `<script>` or `style="..."` in templates, and no third-party origins: the Content Security Policy is `'self'` only. Put CSS in static files and JavaScript in `static/js/`.
- Escape all user and model text (Django autoescaping); never mark user input `safe`.
- Public forms extend `core.spam.SpamProtectedForm` and are rate limited (`core.spam.rate_limited`).
- Log security events on the `security` logger with ids and addresses, never passwords, tokens, or message contents.
- Staff pages live in the admin (`core.admin_site.StaffAdminSite`), which requires staff status and two-factor login when `STAFF_MFA_REQUIRED` is on.
- Money is `DecimalField`, never float. Times are timezone-aware (`USE_TZ = True`). Prices, availability, and totals are calculated and validated on the server, never trusted from the browser.
- Limited resources (time slots, stock) must not be double-booked: enforce it with database constraints, not only in Python.
- Payment card data never touches this application: use the provider's hosted checkout and verify webhook signatures.

## Secrets

- Keep all credentials in environment variables (`.env` locally, which is git-ignored). Add every new variable to `config/settings.py`, `.env.example`, and the table in `docs/DEVELOPER.md`.
- Never commit credentials, connection strings, keys, database host names, or customers' personal data, including in docs, tests, fixtures, or screenshots. The repository is public.

## Frontend

- Read and follow the `frontend-design` skill before implementing or reshaping UI.
- Use the tokens in `static/css/app.css` (`--color-*`, `--font-*`, `--space-*`); don't hardcode other colors.
- Extend `templates/base.html`, reuse `templates/components/`, and use named URLs and `{% static %}`.
- Keep pages responsive, keyboard accessible, readable at WCAG AA contrast, and respectful of `prefers-reduced-motion`.
- Images: the owner's originals go in `src/images/` and are converted with `manage.py optimize_images`; any other image must be free to use and recorded in `static/img/CREDITS.md`. Fonts are self-hosted in `static/fonts/` with their license.
- User-facing text is in the site's language (`LANGUAGE_CODE`). Shared interface strings use `{% translate %}` / `gettext`.

## Code design

- Thin views; business rules in a module's `services.py`, testable without HTTP. Other modules call those services instead of touching another module's models (for example, `crm.services.upsert_contact`).
- External services (email, payments, AI, storage) sit behind a small adapter so tests can replace them; tests never call real external services.
- Keep modules small, with single responsibilities; avoid unrelated refactoring.

## Working practices

- Implement only the requested scope.
- Every behavior change comes with tests (`python manage.py test`). Database tests need PostgreSQL.
- Before committing: `ruff check .`, `ruff format --check .`, tests, and `manage.py check --deploy` with production settings (CI runs all of these plus bandit, pip-audit, and gitleaks).
- Record user-visible changes in `CHANGELOG.md`. Use the pull request template's risk and rollback notes for anything beyond a small fix.
- Report actual verification results. Do not claim a check passed unless it ran and passed.
