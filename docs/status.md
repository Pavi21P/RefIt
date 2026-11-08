# Project status — November 8, 2026

## Implemented

Python/Django application with a gallery based on the supplied layout references; account signup/login/logout and password changes; private filesystem image storage; folder creation/rename/removal; image moves, notes, custom tags and search; favorites; original downloads; recoverable Trash; upload selection, clipboard-image paste and drag/drop handlers; responsive light/dark themes.

The guest gallery contains attributed public-domain artwork. Real accounts start empty.

## Verification

- 28 Django tests pass, including ownership boundaries, private downloads, CSRF enforcement, image-format validation, invalid and oversized files, database-failure cleanup, organization, and logout/login persistence.
- Isolated Chromium workflow passes signup, folder creation, multiple uploads, tag search, edits, downloads, favorites, Trash/restore, paste/drop events, theme persistence, mobile menu/overflow, and logout/login persistence.
- Three occupied columns at desktop width and two columns at 390px mobile width verified; desktop light/dark and mobile screenshots reviewed.
- No JavaScript page errors in the browser workflow.
- Ruff, JavaScript syntax, dependency consistency, migration drift, static collection, and Django production security checks pass.
- Browser tests use a temporary database/media directory. Test accounts and uploads are not part of the real library or the Git repository.

## Remaining boundaries

- Color picking / palette extraction: deferred at the user's request.
- Native OS clipboard and file-manager drag behavior: browser event paths are tested; manual OS integration acceptance remains.
- Hosted deployment is not provisioned. Local data persists on this installation. A public service requires Python hosting, persistent storage, HTTPS, backups, disk monitoring, and signup abuse controls.
- Self-service password recovery and email verification are future work. An operator can use Django's changepassword command locally.
- There is no image-count cap. Capacity depends on disk space. Per-image limits are 25 MB and 40 megapixels.

See README.md for startup and deployment instructions. Continue with real, meaningful commits as features are added; do not manufacture activity.
