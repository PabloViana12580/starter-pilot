## Change

What changes and why (link the issue if there is one).

## Risk and rollback

- Risk: low / medium / high, and what could break.
- Database migration: none / additive / destructive (destructive needs a backup first).
- Rollback: how to undo it (revert the commit, redeploy the previous release, restore a backup).

## Checks

- [ ] Tests added or updated for the changed behavior, and `python manage.py test` passes
- [ ] No secrets, personal data, or database hosts in the diff
- [ ] New tables get row level security automatically (dbcheck passes)
- [ ] User-facing text in the site's language; docs and CHANGELOG updated
