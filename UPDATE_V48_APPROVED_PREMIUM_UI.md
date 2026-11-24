# ShortMint Studio v48 — Approved Premium UI in Code

This release implements the approved dark navy / orange sparkle website visual direction as real frontend code, based on the full v47 project.

## Files for an existing GitHub repository
Copy the six files from the **Replace Only** ZIP to the same paths in your repository:

- `static/index.html` — matching dashboard/editor banners, page headings, and functional quick navigation
- `static/shortmint-ui-v48.css` — the new responsive design system
- `static/shortmint-ui-v48.js` — the new upload shortcut, attached to the existing file input
- `static/sm48-mountain.svg` — decorative hero visual
- `static/sm48-sunset.svg` — decorative hero visual
- `static/sm48-food.svg` — decorative hero visual

Commit all six files together and redeploy on Render; hard-refresh the browser after deployment. This is a frontend-only update. No `DATABASE_URL` or other environment variables were changed.

## Functional behavior

Existing login/invite/promo accounts, Google account migration, credits, admin functions, client messages, exports (540p/720p/1080p), captions, and automatic download remain implemented by the pre-existing scripts and server. Cards use actual account/project data; screenshot sample project counts are intentionally not inserted.

The three hero video thumbnails are decorative illustrations, **not actual user results or view counts**. The processing card directs users to the existing Create Shorts processing interface; it does not pretend to show nonexistent background jobs. Elements such as 2FA, upload-as-you-type auto-save, and uploaded-file attachments in messages shown in concept mockups are **not added as features** by this visual release.

## Testing

- HTML hooks for login, file upload, credit sections and messages retained.
- CSS parsed successfully with no parse errors.
- Desktop and 390px mobile previews generated from fully inlined styles; no horizontal overflow observed.
- 13 focused backend regression tests passed (credit follow-up, orders/messages, voice removal, 1080p max).
- Broader test suite timed out in integration tests and is not claimed to have passed in full.
- Live Render deployment still requires validation. Existing server-side errors (including HTTP 500) require backend logs and are not resolved by UI changes.

## Data safety

The full repository archive omits runtime databases, secrets, `.env`, pytest caches and uploaded videos. Keep the existing persistent PostgreSQL `DATABASE_URL` on Render; don't reset your database when deploying.
