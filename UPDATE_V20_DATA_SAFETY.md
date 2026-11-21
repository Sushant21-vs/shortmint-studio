# ShortMint Studio v20 — Simplified Creator + Data Safety

## What changed
- Removed the large optional Campaign Editing Toolkit in Create Shorts. It was only a manual notes form.
- Added a prominent Owner-only **Download private backup / Restore a backup** panel in Admin.
- Backups keep member accounts (with salted password hashes), invitations, credits, requests, and contact settings. Files do NOT include uploaded videos.
- Export-status checks now poll about every 2.5 seconds and back off up to 30 seconds on temporary errors such as HTTP 429, with fewer alerts.
- Admin's Members, Pending requests, and Active invitations counters still show real server data. Normal web-page refresh does not delete data.

## ⚠️ IMPORTANT — FREE RENDER IS NOT PERSISTENT
Render Free has temporary local storage. Data saved in `shortmint.sqlite3` can disappear when the instance restarts or redeploys. These code changes do NOT prevent that. You must use an external persistent database (or paid disk) to prevent automatic resets.

## Before deploying
A redeploy itself may erase accounts, invitations, credits, and uploads already on your current Render instance. The old version did not have the backup endpoint; there is no guarantee those records can be recovered. If important live user data exists, do not redeploy until you have safely migrated it to persistent storage.

## After deployment — manual recovery procedure
1. Log in as owner and open **Admin Panel → Account Data Safety** (near the top).
2. Click **Download private backup** after creating accounts/invitations or changing credits. Store the .sqlite3 backup privately on your PC and in a secure backup location.
3. If Render loses data and resets to an empty owner account, log in as owner, click **Restore a backup**, select the previously downloaded file and confirm. Members can log in again with their previous passwords.
4. Never upload the backup to public GitHub, send it to friends, or expose it as a download link; it contains personal data and password hashes. It does not include videos.
5. Restoring replaces members, invitations, credits and requests currently stored on that instance. Export a fresh backup first if current data matters.

To eliminate manual recovery, migrate the member/credit data to a persistent hosted PostgreSQL database, such as Supabase, and then test database migration and backup/restore end-to-end. This migration is not included in v20.

## Files to upload
- `app.py` (root) — replace
- `admin_backup.py` (root) — add
- `static/index.html` — replace
- `static/app.js` — replace
- `static/spacious.css` — replace
- `static/account-safety.js` — add

Keep all other existing project files. Commit to GitHub only once you're prepared for the redeploy and its data-loss risk.
