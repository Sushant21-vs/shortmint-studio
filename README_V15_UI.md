# ShortMint Studio v15 — Open Canvas UI

This release is a visual redesign of the existing ShortMint Studio v14. It does **not** change the Python backend, accounts, credit ledger, video encoder, upload limits, or export rules.

## Upgrade an existing GitHub repository

Only three files are required:

1. Replace `static/index.html`.
2. Add `static/spacious.css`.
3. Add `static/spacious.js`.

Commit to your GitHub repository. The latest stylesheet and script URLs contain a `v=15.0.0` version to help bypass the browser cache. After Render finishes deploying, use Ctrl+Shift+R.

Do not delete or rename your existing `styles.css`, `dashboard.css`, `premium.css`, `source-studio.css`, `multi-upload.css`, `montage.css`, `dashboard.js`, `app.js`, or `premium.js`. They still supply essential functionality.

## What changed

- A bright, editorial-style canvas with a charcoal navigation sidebar and cinematic hero section.
- More breathing room, bigger typography, clearer editing controls and higher-contrast form inputs.
- Three key dashboard statistics are visible; the other three are inside **More insights**.
- Creator tips are neatly tucked into an accessible disclosure to reduce clutter.
- Enlarged upload card and more focused editing layout; 20-video batch workflow preserved.
- Mobile responsive layouts, keyboard focus, reduced-motion support and a working day/night switch.
- All existing visible pages are styled consistently: Dashboard, Create Shorts, Credits, Buy Credits and Admin.
- Existing login and invite contact configuration are preserved.

## Hosting warning

Render Free storage is ephemeral. Redeploying can erase the local SQLite accounts, settings, credits and uploaded videos. Back up data **before** you deploy. Use persistent hosting and backups for paid customer accounts.

### Credits

Made by Sushant Hero.
