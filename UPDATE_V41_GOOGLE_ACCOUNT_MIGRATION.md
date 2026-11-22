# ShortMint Studio v41 — Migrate existing Google-only members

## What changes
- Login page now has **Previously used Google sign-in? Recover your account**.
- Eligible old Google-only users provide their previously verified Gmail, receive a six-digit single-use code by email, and set a new password. Then they sign in with their original **username** and new password.
- The migration updates the **original user record**. Credits, ledger, project ownership and history are retained; no new signup and no IP signup restriction.
- New users continue using **invite/promo code registration**. Google Login is still disabled.
- Unknown emails get a generic response to avoid disclosing who has an account. Requests and verification attempts are rate-limited across app restarts using the existing persistent database. Codes expire in ten minutes and allow five tries.
- Password changes invalidate existing sessions for the migrated account.

## Required Render Environment configuration
1. **Back up your persistent Neon/PostgreSQL database first.** Don't overwrite a deployed database with any ZIP.
2. Sign up for **Resend** and verify a domain you control so you can send emails. Create a secret API key.
3. Set the environment variables in Render's dashboard (not GitHub):
   - `RESEND_API_KEY`: Resend's secret API key.
   - `SHORTMINT_FROM_EMAIL`: a valid sender on your verified domain (e.g. `ShortMint <no-reply@yourdomain.com>`).
   - `SHORTMINT_RECOVERY_SECRET`: a random 32+ character secret; keep stable between redeployments.
4. Keep your original `DATABASE_URL` pointed to the same persistent database; keep your owner username/password.
5. Replace the files included in the v41 Replacement ZIP, commit, and redeploy in Render.
6. Test the recovery flow with a *real legacy Google-only account* and the exact old Google email. Test another nonexistent address for generic response and a new invite/promo user to ensure onboarding still works.

## Important security and deployment details
- This requires access to the original Google email. A user who lost access needs a separate owner-assisted identity verification process; do not manually change their password using only an unverified email claim.
- Unverified account email, disabled accounts, and accounts that already have passwords are not migratable through this flow. For old Google-only users with no stored email, contact the owner.
- On Render the email is sent using Resend's HTTPS API, rather than SMTP. Without the configured environment variables, the endpoint fails closed with a `503` message; nothing is silently emailed.
- An account's original `username` is shown **only after** successful email verification.
- The email inbox or spam folder may take time to receive the verification message. Code expires after ten minutes.
- Google OAuth remains disabled; it is **not** a new login method.
- Existing account records and credited balance live in PostgreSQL. Video files stored only in Render's ephemeral filesystem may not survive earlier deployments even though their account/project IDs are preserved.
- If Resend fails to send a code, that issued code is removed server-side; check provider setup/logs.
