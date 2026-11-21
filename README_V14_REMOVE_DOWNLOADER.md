# ShortMint Studio v14 — Download Videos menu removed

This is the complete ShortMint Studio project based on v13, with the non-working standalone **Download Videos** page removed from the website UI.

## What changed
- Removed **Download Videos** from left navigation and quick actions (Ctrl+K).
- Removed the download-page form, error panel, and dashboard download promotion.
- Removed the corresponding **daily download credits** setting from the Admin UI.
- Replaced a download promotional button with **My Credits**.
- Removed unused `downloads.js` and `downloads.css` references and files.
- Kept **Create Shorts**, multi-video upload (up to 20 per batch), montage editing, video export, **Download Short MP4**, and **Download all ZIP**.
- Preserved login, account credits, invite codes, purchase inquiries, and Made by Sushant Hero.

## Update your existing GitHub repo
You only need these 3 files from the **Replace Only** ZIP:

1. `static/index.html`
2. `static/dashboard.js`
3. `static/premium.js`

Replace each at the same path on GitHub, commit to `main`, and let Render redeploy. Then refresh with **Ctrl+Shift+R**. There is no need to replace the backend or account database.

> The old `static/downloads.js` and `static/downloads.css` can remain on GitHub: this updated HTML does not load them. To clean up the repository you may delete them, but this is optional.

## Note on API routes
This update removes the **public website option/UI**, not every legacy download API endpoint. Those backend routes remain in the full source for compatibility. If you later need to disable them as well, that is a separate backend change.

## Hosting
Render Free uses ephemeral storage; redeployment can reset accounts, credits, and uploaded video files. Back up important data before committing changes.
