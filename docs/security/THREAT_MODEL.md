# Threat model

A lightweight model (STRIDE) for this website. Review it whenever a module is added or a new kind
of data is stored.

## What we protect (data inventory)

| Data | Where | Who can see it | Sensitivity |
| --- | --- | --- | --- |
| Staff accounts (username, Argon2id password hash, authenticator secret) | `auth_user`, `otp_totp_totpdevice` | Administrators | High |
| Sessions and sign-in attempts (addresses, usernames) | `django_session`, `axes_*` | Administrators | Medium |
| Customers' contact details and messages (when the CRM is installed) | `crm_*` | Staff with CRM permissions | Personal data |
| Site content and images | repository (`templates/`, `static/`, `src/images/`) | Public | Public |
| Secrets (secret key, database and email passwords) | hosting platform environment, local `.env` | Developers, platform | High |

## Trust boundaries

1. Visitor browser > website (public pages, contact form): untrusted input.
2. Staff browser > administration: authenticated with password and two-factor.
3. Website > PostgreSQL provider: TLS, credentials from the environment.
4. Website > email provider: TLS, credentials from the environment.
5. Developer > GitHub > hosting platform: code review, CI gates, secrets never in the repository.

## Threats and mitigations

| STRIDE | Threat | Mitigation (see CONTROLS.md) |
| --- | --- | --- |
| Spoofing | Password guessing or stuffing against staff accounts | C6 passwords, C7 lockout, C9 two-factor, C20 logging |
| Spoofing | Faking client addresses to bypass lockout and rate limits | C19 trusted proxy count |
| Tampering | Cross-site request forgery on staff actions | C12 CSRF, C11 SameSite cookies |
| Tampering | Malicious code injected in pages (XSS) | C17 autoescaping, C14 CSP without inline code |
| Repudiation | Staff actions without a trace | Django admin history, C20 security log |
| Information disclosure | Database reachable through the provider's HTTP API | C4 row level security, C5 isolation |
| Information disclosure | Data intercepted in transit | C3 database TLS, C13 HTTPS and HSTS, C11 cookies |
| Information disclosure | Secrets or personal data committed to the public repository | C2 secret scanning, AGENTS.md rules |
| Information disclosure | Photo metadata revealing locations | C23 metadata removal |
| Information disclosure | Error pages leaking internals | C21 generic errors, C1 DEBUG off |
| Denial of service | Contact form flooding, log flooding | C18 rate limits, CSP report limits |
| Elevation of privilege | Non-staff or unverified staff reaching the administration | `StaffAdminSite`, C9 two-factor gate |
| Supply chain | Vulnerable or tampered dependencies, compromised CI actions | C24 hashed pins and audits, C25 SBOM, C28 pinned actions |

## Assumptions

- The hosting platform terminates TLS and sets `X-Forwarded-Proto` / `X-Forwarded-For`
  (configure `DJANGO_TRUSTED_PROXY_COUNT`).
- Staff keep their authenticator phones and passwords private; the owner reviews staff accounts
  when people leave (deactivate the account).
- The PostgreSQL provider encrypts data at rest and keeps its own backups.
