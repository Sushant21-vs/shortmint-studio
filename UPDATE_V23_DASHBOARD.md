# ShortMint Studio v23 — Creator Desk Dashboard

This release **redesigns the actual signed-in Dashboard**. Earlier v21–v22 updates focused on Login and Admin; this release replaces the old dark “Make room for big ideas” dashboard hero.

## For your existing GitHub repository

Replace or add these files, keeping their paths:

- `static/index.html` — replace
- `static/creator-dashboard-v23.css` — add
- `static/creator-dashboard-v23.js` — add

No backend, database, account, export, credit, admin, or video-processing files are modified by this update.

## What's new

- Cream and coral/orange creator dashboard with a completely new hero layout
- Animated vertical-video preview artwork (decorative, not a video player)
- Connected “Create a Short” and “See my projects” actions
- Restyled credit, project, and generated Short statistics using the existing live IDs
- Restyled quick start, credit access, project list, and mobile layout
- Existing light/night mode switching retained
- Supports reduced-motion preference

## Test notes

- All 35 included backend tests pass locally.
- Rendered at 1550px desktop and 415px mobile; no horizontal overflow.
- Preview numbers shown in screenshots are illustration only; deployed statistics still come from the real backend.

## Before deploying

Render Free uses temporary local storage. **Download the private database backup in Admin → Account Data Safety** before committing anything to GitHub; a redeploy may erase member accounts, invitations and credits unless you have persistent storage. Save your backup privately, never in GitHub.

Commit the changes, allow Render to redeploy, then press Ctrl+Shift+R in Chrome to refresh.
