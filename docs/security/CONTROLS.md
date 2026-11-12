# Security and quality controls

What protects this application, where it is implemented, how it is verified, and how it maps to
the frameworks the project follows. "Mapped to" means the control contributes to that requirement
or practice; it is not a claim of compliance or certification, which apply to organizations and
need an audit.

Target: **OWASP ASVS 5.0 level 1**, plus the level 2 requirements listed below. Requirement IDs
come from the official ASVS 5.0.0 export (github.com/OWASP/ASVS). NIST SSDF = SP 800-218 v1.1
practices; NIST CSF = CSF 2.0 subcategories; ISO 27002 = ISO/IEC 27002:2022 controls.

## Controls

| # | Control | Implementation | Verified by | ASVS 5.0 | SSDF | CSF 2.0 | ISO 27002 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | Secure configuration by default: DEBUG off unless set, secret key required, hosts from env | `config/settings.py` | `core/tests/test_settings.py`, CI `check --deploy` | V13.4.2 | PW.9 | PR.PS-01 | 8.9 |
| C2 | Secrets only in environment variables; repository scanned | `.env` (git-ignored), `.env.example` | CI gitleaks, GitHub secret scanning with push protection | V13.3.2 | PS.1 | PR.DS-01 | 5.17, 8.4 |
| C3 | Encrypted database connections (TLS required except localhost) | `database_from_env()` | `test_settings.DatabaseConfigTests`, `manage.py dbcheck` | V12.3.1 | PW.9 | PR.DS-02 | 8.24, 8.20 |
| C4 | Row level security on every table (no direct API access to data) | `core/rls.py` (after every migrate) | `core/tests/test_database.py`, `dbcheck` | V8.3.1 | PW.9 | PR.AA-05 | 8.3, 5.23 |
| C5 | One database per project (tenant isolation) | `dbcheck` isolation check | `test_database.DbcheckCommandTests` | V8.2.2 | PO.5 | PR.IR-01 | 8.31 |
| C6 | Passwords: min 12 characters, common-password list, no composition rules, Argon2id hashing | `AUTH_PASSWORD_VALIDATORS`, `PASSWORD_HASHERS` | `test_auth.PasswordStorageTests` | V6.2.1, V6.2.4, V6.2.5, V6.2.9, V11.4.2 | PW.5 | PR.AA-01 | 5.17, 8.5 |
| C7 | Brute-force protection: lockout per username and address | django-axes settings, `registration/locked_out.html` | `test_auth.LoginTests.test_lockout_after_repeated_failures` | V6.3.1, V6.1.1 | PW.5 | PR.AA-03 | 8.5 |
| C8 | Generic sign-in errors (no account enumeration) | Django `AuthenticationForm` | `test_auth...test_wrong_password_gives_one_generic_message` | V6.3.8 (L3) | PW.5 | PR.AA-03 | 8.5 |
| C9 | Two-factor sign-in (TOTP) for staff when personal data is stored; codes single-use; reset only by an administrator | `core/mfa.py`, `core/account_views.py`, `StaffMFAMiddleware`, `StaffAdminSite`, `reset_mfa` | `core/tests/test_mfa.py` | V6.3.3, V6.5.1, V6.5.3, V6.5.5, V6.4.4 | PW.5 | PR.AA-03 | 8.5, 8.2 |
| C10 | Sessions: new session at sign-in, 30 min idle timeout, 12 h absolute lifetime, ended on sign-out or account deactivation | `SESSION_*`, `SessionLifetimeMiddleware`, `StaffLogoutView` | `test_auth.SessionLifetimeTests`, `LogoutTests` | V7.2.4, V7.3.1, V7.3.2, V7.4.1, V7.4.2 | PW.5 | PR.AA-03 | 8.5 |
| C11 | Cookies: Secure, HttpOnly, SameSite=Lax, `__Host-` prefix in production | `SESSION_COOKIE_*`, `CSRF_COOKIE_*` | `test_settings.ProductionSettingsTests` | V3.3.1, V3.3.2, V3.3.3, V3.3.4 | PW.9 | PR.DS-02 | 8.24 |
| C12 | CSRF protection on every form, POST-only sign-out | Django CSRF middleware | `test_auth.LogoutTests`, CRM form tests | V3.5.1 | PW.5 | PR.DS-02 | 8.26 |
| C13 | HTTPS only: redirect, HSTS 1 year with subdomains | `SECURE_SSL_REDIRECT`, `SECURE_HSTS_*` | `test_headers` | V3.4.1, V4.1.2, V12.2.1 | PW.9 | PR.DS-02 | 8.24 |
| C14 | Content Security Policy `'self'` only, no inline code, frame-ancestors none, violations reported | django-csp, self-hosted Bootstrap and fonts, `core.views.csp_report` | `test_headers.SecurityHeaderTests` | V3.4.3, V3.4.6, V3.2.1 | PW.5 | PR.PS-01 | 8.26 |
| C15 | Other headers: nosniff, Referrer-Policy same-origin, COOP, X-Frame-Options DENY, Permissions-Policy | settings, `PermissionsPolicyMiddleware` | `test_headers` | V3.4.4, V3.4.5 | PW.9 | PR.PS-01 | 8.26 |
| C16 | Clear browser data at sign-out | `Clear-Site-Data` on `StaffLogoutView` | `test_auth...test_logout_tells_the_browser_to_clear_site_data` | V14.3.1 | PW.5 | PR.DS-10 | 8.12 |
| C17 | Output encoding: Django autoescaping; QR codes generated as inline SVG without scripts | templates, `core/mfa.py` | `test_mfa...test_qr_code_is_inline_svg_without_scripts`, CRM escaping | V1.2.1, V3.2.2 | PW.5 | PR.DS-10 | 8.28 |
| C18 | Anti-automation on public forms: honeypot, minimum fill time, per-address rate limits | `core/spam.py` | `core/tests/test_spam.py`, CRM contact form tests | V2.4.1 | PW.5 | DE.CM-09 | 8.16 |
| C19 | Trusted client address behind proxies (no spoofing of lockout/rate limits) | `core/net.py`, `DJANGO_TRUSTED_PROXY_COUNT` | `test_spam.ClientIpTests` | V15.3.4 | PW.9 | PR.PS-01 | 8.20 |
| C20 | Security event logging (sign-in, failures, lockouts, two-factor, CSP, spam), UTC timestamps, no secrets | `core/signals.py`, `LOGGING`, `core/logformat.py` | `test_operations.SecurityLogTests` | V16.3.1, V16.3.3, V16.2.1, V16.2.2, V16.2.5, V16.4.1 | RV.1 | PR.PS-04, DE.CM-09 | 8.15, 8.16 |
| C21 | Generic error pages without details; standalone 500 page | `templates/4xx-5xx.html`, `error_base.html` | `test_operations.ErrorPageTests` | V16.5.1, V16.5.3 | PW.9 | PR.PS-01 | 8.26 |
| C22 | Health and readiness probes | `/healthz`, `/readyz` | `test_operations.ProbeTests` | V16.5.2 | PW.9 | DE.CM-09 | 8.16 |
| C23 | Image metadata removed (location, camera) before publishing | `optimize_images` | `test_images` | V14.2.3 | PW.5 | PR.DS-01 | 5.34 |
| C24 | Dependency pinning with hashes; weekly updates; vulnerability audit in CI | `requirements*.txt` (pip-tools), Dependabot, pip-audit | CI | V15.1.1, V15.2.1 | PW.4, RV.1 | ID.RA-01, PR.PS-02 | 8.8 |
| C25 | Software bill of materials per build | pip-audit CycloneDX | CI artifact `sbom` | V15.1.2 | PS.3 | ID.AM-08 | 8.8 |
| C26 | Static analysis and code scanning | ruff (incl. security rules), bandit, CodeQL default setup | CI, GitHub code scanning | - | PW.7 | ID.RA-01 | 8.29 |
| C27 | Automated tests and coverage gate on PostgreSQL | `manage.py test`, coverage `fail_under` | CI | - | PW.8 | PR.PS-06 | 8.29 |
| C28 | Protected main branch (no force-push/deletion), pinned CI actions, least-privilege CI token | GitHub ruleset, `.github/workflows/ci.yml` | GitHub settings | - | PS.1, PO.3 | PR.PS-06 | 8.4, 8.32 |
| C29 | Vulnerability disclosure and remediation time frames | `SECURITY.md`, private vulnerability reporting | GitHub settings | V15.1.1 | RV.1, RV.2 | ID.RA-08 | 8.8, 5.24 |
| C30 | Change, release, incident, backup, and secret rotation procedures | PR template, `CHANGELOG.md`, tags, `docs/operations/RUNBOOK.md` | Review | - | PO.1 | RS.MA-01, RC.RP-01, PR.DS-11 | 8.32, 5.26, 8.13 |
| C31 | Threat model and data inventory | `docs/security/THREAT_MODEL.md` | Review at each module change | V14.1.1 | PW.1 | ID.AM-07 | 5.34, 8.26 |

Modules add rows for their own controls below.

## Module controls

| # | Control | Implementation | Verified by | ASVS 5.0 | SSDF | CSF 2.0 | ISO 27002 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CRM-1 | CRM: contact form validation and limits (lengths, email format) | `crm/forms.py` | `crm/tests/test_contact_form.py` | V2.2.1 | PW.5 | PR.DS-10 | 8.26 |
| CRM-2 | CRM: spreadsheet formula injection neutralized in CSV exports | `crm/exports.py` | `crm/tests/test_admin.py` | V1.2.10 (L3) | PW.5 | PR.DS-10 | 8.28 |
| CRM-3 | CRM: marketing consent recorded with time and source; per-person data export for access requests | `crm/models.py`, `crm/exports.py` | `crm/tests/test_services.py`, `test_admin.py` | V14.2.4 | PW.1 | ID.AM-07 | 5.34 |
| CRM-4 | CRM: email header injection prevented in notifications; mail outage never loses a message | `core/notifications.py`, `crm/services.py` | `crm/tests/test_services.py` | V16.5.2 | PW.5 | PR.DS-01 | 8.26 |
| CRM-5 | CRM: exports require the view permission and are logged | `crm/admin.py` | `crm/tests/test_admin.py` | V8.2.1, V16.3.3 | PW.5 | PR.AA-05 | 5.15, 8.15 |

When you remove a module, delete its rows; when you add one, add its rows from the module.

## Other frameworks

| Framework | How it applies here |
| --- | --- |
| CIS Benchmarks | Applicable parts only: the CIS PostgreSQL Benchmark's TLS and access recommendations (C3, C4, least-privilege role recommended for production) and the CIS Software Supply Chain Security Guide's source, dependency, and pipeline recommendations (C24-C28). Operating-system and container benchmarks apply to the hosting platform, not this repository. |
| ISO/IEC 25010:2023 | Security: C6-C21. Reliability (faultlessness, availability, recoverability): C22, C27, C30. Maintainability (modularity, testability, analysability): module structure, C26, C27. Interaction capability: accessibility basics in templates (labels, focus, skip link, contrast). Compatibility and flexibility: hosting-agnostic settings, `Procfile`, `Dockerfile`. |
| ITIL 4 | Change enablement: PR template with risk and rollback, CI gate. Release management: SemVer tags, `CHANGELOG.md`, GitHub releases. Incident management, information security management: `RUNBOOK.md`, `SECURITY.md`. Service configuration management: `.starter.json`, pinned dependencies. |
| NIST CSF 2.0 Govern | Roles and policies are the owner's; this repository provides the technical evidence (this file, the threat model, the runbook). |

## Known gaps and decisions

| Requirement | Status |
| --- | --- |
| ASVS V6.2.12 (L2) breached-password check | Not implemented: it needs a third-party service; the common-password list (C6) covers L1. |
| ASVS V12.3.2 (L2) validate the database server certificate | Recommended per provider: `DB_SSLMODE=verify-full` with `DB_SSLROOTCERT` (provider CA file, or `system`). Default is `require`. |
| ASVS V13.3.1 (L2) secrets vault | Secrets live in the hosting platform's encrypted environment variables. |
| ASVS V16.4.3 (L2) logs shipped to a separate system | Logs go to stdout; connect the platform's log drain per deployment. |
| ASVS V7.4.5 / V7.5.2 (L2) listing and ending individual sessions | Deactivating an account ends all its sessions (C10); per-session management is not built. |
| ASVS V3.4.3 CSP report-uri | Uses `report-uri` (widely supported) rather than the newer Reporting API. |
