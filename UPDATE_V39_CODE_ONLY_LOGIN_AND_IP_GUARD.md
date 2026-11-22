# ShortMint Studio v39 — Code-only access and one signup per IP

## Changes
- Removed Google sign-in from the UI and API (requests to `/api/auth/google` or `/api/auth/google-config` now return 404).
- **New account:** choose **Join with code**, select **Invitation** or **Promo**, and enter username, password (10+ characters), and code.
- **Returning member:** sign in with username and password. Codes **never act as a reusable password**.
- **Promo signup:** validates expiry/active/max uses in the same database transaction; grants starter credits plus promo credits and records redemption once.
- **Invite signup:** consumes one unused owner invite and awards the normal welcome credits.
- **1 account per IP:** enforces a unique **hashed signup IP** for new member accounts with a persistent SQLite/PostgreSQL unique index. Owner account exempt. Existing accounts continue to sign in; restriction is not applied retroactively.
- Preserved video editor, export reminder, credits, projects, new logo and dashboard visuals.

## Deploy
1. Back up Neon/PostgreSQL before upgrading. Do not upload real database backups or `.env` to GitHub.
2. Upload the replacement ZIP files to the same relative GitHub paths (including `accounts.py`, `pg_storage.py`, `growth.py`, `admin_backup.py`, `static/index.html`, `static/dashboard.js`, `static/growth-v27.js`, `static/shortmint-code-access-v39.css`, `static/privacy.html`, `requirements.txt`, `render.yaml`, `.env.example`).
3. Commit and let Render rebuild. Keep your `DATABASE_URL`, `OWNER_USERNAME`, and `OWNER_PASSWORD` settings in Render. `GOOGLE_CLIENT_ID` and `OWNER_GOOGLE_EMAIL` are no longer used.
4. In Admin, generate invitations or promos for new users. Each promo can be used only up to its configured limit.
5. Sign out, hard-refresh, and test new registration from a real client device.

## Important limitations
- IP addresses are **not identities**. Family members, schools, offices, and mobile-carrier NAT can share public IPs, so the signup block may affect unrelated people; VPNs and changing networks can bypass it. This is a deterrent, not reliable uniqueness or fraud prevention.
- The server takes the client address supplied by Uvicorn's trusted-proxy handling. If that address belongs to a verified Cloudflare proxy, ShortMint can use `CF-Connecting-IP` (overwritten by Cloudflare) for the real visitor address. Only trust HTTP forwarding headers from your actual reverse proxy. `cloud_start.py` now trusts forwarded headers only from common internal proxy IP ranges by default. Cloudflare network ranges are checked in `accounts.py` and require periodic updates. If Render uses another trusted proxy address, configure `SHORTMINT_TRUSTED_PROXY_IPS` to its actual address/range; never use `*` on an internet-reachable server. Verify with two real clients using the same public IP and one using a different public IP.
- Existing account records do not have a known historical signup IP, so they cannot be backfilled reliably. New signup limits start with this deployment.
- Existing Google-only users lack a local password and **cannot sign in** after this upgrade. Arrange owner-verified account migration before deploying if you have existing Google members; **creating a new account will not automatically recover their old credits/projects**.
- The stored hash of an IP still constitutes potentially identifying information; privacy notice has been updated. Review applicable privacy obligations.
- Promo codes are shared access tokens for **sign-up**, not sufficient authentication for returning users.
