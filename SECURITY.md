# Security policy

## Reporting a vulnerability

Please report security problems privately through GitHub: the repository's
**Security** tab > **Report a vulnerability**. Do not open a public issue.
Include what you found, how to reproduce it, and the impact you expect. You
will get an acknowledgement within 3 working days.

## Supported versions

Only the latest release on `main` receives security fixes.

## How this project handles vulnerabilities

| Severity (CVSS) | Fix or mitigate within |
| --- | --- |
| Critical (9.0-10) | 2 days |
| High (7.0-8.9) | 7 days |
| Medium (4.0-6.9) | 30 days |
| Low (0.1-3.9) | next planned release |

These time frames also apply to vulnerable third-party packages, which are
found by `pip-audit` in CI on every push and by Dependabot alerts. Dependency
updates arrive weekly as Dependabot pull requests.

The security controls and how each one is verified are listed in
[docs/security/CONTROLS.md](docs/security/CONTROLS.md); the threat model is in
[docs/security/THREAT_MODEL.md](docs/security/THREAT_MODEL.md).
