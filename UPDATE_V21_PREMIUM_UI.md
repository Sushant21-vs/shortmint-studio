SHORTMINT STUDIO v21 — AURORA EXPERIENCE (21 November 2026)

Premium UI/UX upgrade only. The editing and database backend are unchanged.

UPDATING YOUR EXISTING GITHUB REPOSITORY
1. Before making any changes, open ShortMint Admin > Account Data Safety and
   download your private backup. Do not put that file in GitHub.
2. Open the repository Sushant21-vs/shortmint-studio.
3. From the v21 Replacement ZIP, replace the following two existing files:
   static/index.html
   static/dashboard.js
4. Add these three new files under static/:
   static/favicon.svg
   static/creator-experience-v21.css
   static/creator-experience-v21.js
5. Commit the changes. Render will normally redeploy when connected to main.
6. Refresh the browser with Ctrl+Shift+R to avoid old cached assets.

WHAT IS NEW
- Transparent, no-black-background orange sparkle favicon.
- Editorial cream/peach login with glass panel, distinctive logo, icons, and
  improved sign-in and invitation design.
- Decorative cloud/mist following the cursor on login, plus small touch bursts.
  The animation ignores pointer input and obeys reduced-motion preferences.
- Owner dashboard with modern hero panel, shortcuts to members/invites/backup,
  upgraded statistic cards, clearer data safety panel.
- Version marker in workspace updated to V21.

WHAT STAYS THE SAME
- Password and invite-code registration, owner contact and WhatsApp links.
- Admin members, credit requests, invitations, contact settings and backup/restore.
- 20-video upload and Shorts editing/export pipelines.
- All storage, credits, account logic, and REST API endpoints.

DATA SAFETY
Render Free has ephemeral local storage. This UI update does NOT fix that.
Your SQLite database, members, invitations, account credits, and uploaded videos
may disappear after a server restart or redeploy unless stored on persistent
storage. Make a private backup BEFORE deploying, and keep it off GitHub.
Use a durable external database for production. A backup only supports recovery.

CHECKS
35 existing backend tests passed. Responsive desktop/mobile browser layout
checked; show/hide password and admin shortcuts checked. Login tab behavior
is backed by original dashboard.js and unchanged; network-backed login not
exercised against live Render in this environment.
