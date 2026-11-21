# ShortMint Studio v16 — Clean centered login

Matches the requested single-card sign-in screen. The marketing panel and decorative orbits are removed; sign-in, invite registration and admin-configured contact remain functional.

## Update an existing GitHub deployment

1. Replace `static/index.html` with the supplied file.
2. Add `static/login-clean.css`.
3. Commit both files to your GitHub repository (main branch).
4. Render should redeploy if automatic deployment is enabled; refresh the website.

This change only updates HTML structure for the login area and isolated login styling. It does not modify `app.py`, the credit system or videos.

## Important on Render Free

Render Free storage is ephemeral; account/credit settings and files can be lost on rebuild/restart. Backup important data before deploying.
