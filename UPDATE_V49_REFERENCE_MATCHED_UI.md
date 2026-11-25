# ShortMint Studio v49 — Reference-Matched UI

This update recreates the approved dark navy / orange-glow concept as real website code.

## What's included

- Rebuilt Dashboard structure: compact header, hero art, live metrics, new-project upload shortcut, processing status, recent projects, account-linked messages, quick actions and generated project gallery.
- Updated Create Shorts upload screen with editable pre-upload defaults for short length, quality (540p / 720p / 1080p), optional speech-to-text captions and auto montage. These preferences are passed to the existing functional editor when a video opens.
- Consistent styling for Settings, Orders & Messages, Buy Credits and the Admin section.
- Responsive phone/tablet layouts and high-contrast notifications.
- Real account/projects/messages/credits data: the example customer conversations, sample project counts and sample performance figures in the design reference are NOT invented or displayed as live data.
- Hero scene artwork is **illustrative decoration**. It does not imply the user's own videos have those views.

## Install update into existing GitHub repo

1. Back up the current version (especially database credentials and server environment settings).
2. Extract `ShortMint_v49_Reference_Matched_Replace_Only.zip`.
3. Upload its `static/` directory contents to the same paths in the GitHub repository, preserving folder structure.
4. Commit to the branch your Render service deploys from and allow Render to redeploy.
5. Hard-refresh your browser (Ctrl+Shift+R).

For a clean deployment, use `ShortMint_Studio_v49_Reference_Matched_Full_GitHub.zip`; it includes application source + this UI update, but no local account database.

## Important notes

- This is a UI and client-side experience update, not a backend or database migration.
- Your existing code/promo signup, Google-only account migration, admin controls, credit orders, messages, automatic download, and maximum 1080p export remain intact.
- Google Login remains removed, and Voice Studio remains removed.
- No fake orders, videos, views, usernames, 2FA, paid checkout or real-time push notifications are added. Functions pictured in the mockup but absent from the existing backend have NOT been advertised as live.
- Live functionality needs a working persistent `DATABASE_URL` configured on Render, as previously required by ShortMint.
- A preexisting Admin Panel HTTP 500 error is not fixed by a visual redesign; check its Render error logs separately.
- The pre-upload defaults are only applied after the user uploads/opens a video. If no file is selected, no export starts and no credits are spent.

## Verification

- HTML DOM parse: IDs unique; required sections present.
- JavaScript syntax checks for `static/dashboard.js` and `static/shortmint-reference-v49.js`.
- Offline visual screenshots created at desktop and mobile widths; no horizontal scroll at 1672px, 1330px and 410px.
- 13 focused regression tests passed: video export limit, credit request follow-up, private order/messages, and processing reminder.
- Live Render deployment and full suite (including video-processing integration tests) have not been validated in this environment.
