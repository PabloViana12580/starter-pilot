# Operations runbook

Practical steps for running the site: releases, backups, incidents, and secrets. Times are in
UTC in the logs.

## Releases and changes

1. Work on a branch; open a pull request using the template (change, risk, rollback, checks).
2. CI must pass. Merge to `main`.
3. Update `CHANGELOG.md`, tag the release (`git tag v0.2.0 && git push --tags`), and create the
   GitHub release from the tag.
4. Deploy, then run `python manage.py migrate` on the server.
5. Check `/readyz` returns `ready` and sign in to the administration.

Rollback: redeploy the previous tag. If the release ran a migration that removed or changed data,
restore the backup taken before it (below).

## Backups and restore

Before any migration that removes or changes data, and at least weekly:

```bash
pg_dump --format=custom --no-owner --file=backup-$(date +%Y%m%d).dump "$DATABASE_URL"
```

Store the file somewhere private (it contains customers' personal data), never in the repository.
Restore into an empty database:

```bash
pg_restore --no-owner --dbname="$TARGET_DATABASE_URL" backup-YYYYMMDD.dump
```

Then run `python manage.py migrate` (row level security is re-applied) and `python manage.py dbcheck`.
Check your provider's own backups too (for example, Supabase's free plan has no point-in-time
recovery, and free projects pause after a week without activity: resume them from the dashboard).

## Incidents

1. **Detect**: `/readyz` failing, errors in the platform logs, `security` log lines (many
   `auth.login_failed` / `auth.locked_out`, `csp.violation`, `spam.rejected`), or a report.
2. **Contain**: if an account may be compromised, deactivate it in the administration (its
   sessions end immediately) and run `python manage.py reset_mfa <username>`. If a secret leaked,
   rotate it (below). If the site is under attack, put it in maintenance at the platform.
3. **Recover**: fix, release with the normal process, restore data from a backup if needed.
4. **Learn**: open an issue (Bug or incident template) with timeline, cause, and follow-ups. If
   personal data was exposed, the owner may have legal duties to notify; document what data,
   whose, and when.

## Rotating secrets

| Secret | How to rotate | Effect |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | Generate a new random value, set it on the platform, redeploy. | Everyone is signed out; form tokens reset. |
| Database password | Reset it at the provider, update `DATABASE_URL`, redeploy. | Brief interruption while the app restarts. |
| Email password / API key | Create a new one at the email provider, update the variable, redeploy, revoke the old one. | None. |
| Staff password | The person changes it in the administration (top right). | Their other sessions end. |
| Lost authenticator phone | `python manage.py reset_mfa <username>` after confirming who is asking. | They set up two-factor again at next sign-in. |

## Locked-out staff

Lockouts expire after `LOGIN_LOCKOUT_MINUTES` (default 15). To unlock sooner, delete the access
attempts for that user in the administration (Axes > Access attempts).
