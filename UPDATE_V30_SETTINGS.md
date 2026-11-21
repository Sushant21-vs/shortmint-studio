# ShortMint Studio v30 — Workspace Settings

This update adds a Settings page accessible from the left sidebar and header. It replaces the on-screen Quick actions search launcher and moon button with a clearly labeled Settings shortcut while retaining Ctrl+K.

Features:
- Daylight / Midnight visual theme (uses existing ShortMint theme system).
- Smooth cloud cursor on/off with CPU savings while disabled.
- Reduce animations preference.
- Read-only username, role, and credits.
- Working privacy policy and sign out links.

Appearance preferences save locally in this browser, not to the Neon member database. Credits and accounts remain server managed.

## Replace
Upload all files from the replacement ZIP to the matching locations in your `shortmint-studio` GitHub repository. Commit to `main` and ensure your new Render service deploys that commit.

Changed files: `static/index.html`, `static/dashboard.js`, `static/shortmint-cloud-v24.js`.
New files: `static/shortmint-settings-v30.css`, `static/shortmint-settings-v30.js`.

This update does NOT change Google OAuth, promo codes, passwords, video export, or the Neon database.
