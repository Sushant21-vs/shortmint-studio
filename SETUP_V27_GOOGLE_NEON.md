# Archived instructions — Google access removed in v39

The Google OAuth instructions below apply to historical v27 builds **only**. Do not enable Google sign-in on ShortMint v39. Follow `UPDATE_V39_CODE_ONLY_LOGIN_AND_IP_GUARD.md` for current setup. PostgreSQL/Neon setup remains relevant.

---

# ShortMint Studio v27 · 100+ Creator Launch

## Read before deploying

v27 changes where ShortMint **account data** lives. On Render Free, the current SQLite database is temporary. You must configure an **external PostgreSQL database** before deploying this version. The included `render.yaml` requires `DATABASE_URL` to prevent a false impression of permanent storage.

**Important:** Your existing members will NOT automatically appear in the new database. Export your old account backup first and import it into the **empty** new database with the instructions below. Uploaded video files and exported MP4s will **still be temporary** on Render Free; PostgreSQL stores identity, credits, promos, purchase inquiries, and session records, not video files.

## 1. Save your existing members

1. While the old site still works, sign in as owner.
2. Go to **Admin Panel → Download private backup**.
3. Save the downloaded `ShortMint_private_accounts_....sqlite3` file privately on your computer (not to GitHub or a public file share).
4. Keep it secure: the database backup includes password hashes, contact settings and member information.

## 2. Create a persistent PostgreSQL database

1. Open https://console.neon.tech/ and create a Neon PostgreSQL project.
2. Choose **Connect** and copy the **pooled connection string** (a `postgresql://...` or `postgres://...` URL with `sslmode=require` and usually `-pooler` in the hostname).
3. This is a **secret**. Paste it only into **Render → shortmint-studio → Environment → DATABASE_URL**. Never put it into GitHub, HTML, a screenshot, or the ZIP.
4. Review Neon's current free-tier quota and backup/restore options; free storage and compute are not unlimited.

## 3. Create Google sign-in

1. Open https://console.cloud.google.com/auth/clients (Google Cloud → Google Auth Platform).
2. Create a project and configure the OAuth app brand/audience.
3. Choose **External** audience and prepare it for **In production** before offering the website to over 100 people. In **Testing**, Google limits the app to explicitly listed test users (up to 100).
4. Create an OAuth Client ID with application type **Web application**.
5. In **Authorized JavaScript origins**, add EXACTLY `https://shortmint-studio.onrender.com` (no trailing slash, no `/login`). If you use a custom domain, add that origin too.
6. Copy the **Web client ID**, which looks like `1234567890-....apps.googleusercontent.com`. Set it in **Render → Environment → GOOGLE_CLIENT_ID**. The client ID is public; it is not the database password.
7. Set `OWNER_GOOGLE_EMAIL` to the verified Google address you personally control **only if** you want that Gmail login to open the owner account. Existing username/password owner login also continues working.
8. Review Google's brand, privacy policy, domain verification and production readiness requirements.

ShortMint uses the official Google Identity Services button. The server verifies the signed ID token with Google's libraries before granting access. The Google password is never sent to ShortMint.

## 4. Configure Render before deploying

Under your existing Render web service → **Environment**, set:

| Variable | Value |
|---|---|
| `DATABASE_URL` | Neon pooled PostgreSQL URL (SECRET) |
| `GOOGLE_CLIENT_ID` | Google Web client ID |
| `OWNER_GOOGLE_EMAIL` | Optional verified owner's Google address |
| `REQUIRE_PERSISTENT_DB` | `1` |
| `OWNER_USERNAME` | SAME username as the old owner |
| `OWNER_PASSWORD` | Owner's private password (never in GitHub) |
| `SHORTMINT_STORAGE_DIR` | `/app/storage-data` (temporary video files) |

Do not use `OWNER_GOOGLE_EMAIL` to link a member's address to the owner. Only use your own Gmail.

## 5. Deploy the code

1. Upload all the files from **ShortMint_v27_Growth_Replace_Only.zip** to the matching paths in your existing GitHub repository.
2. Make sure new files such as `growth.py`, `pg_storage.py`, `static/growth-v27.js`, `static/growth-v27.css` and `static/privacy.html` are included.
3. Commit changes to the main branch; Render redeploys the web service.
4. Check `/api/health` and `/api/hosting/status`. The latter should say `"persistent_accounts":true`.
5. If the service doesn't start, check the Render logs for database connection errors and confirm environment variable spelling. **Do not disable `REQUIRE_PERSISTENT_DB` to work around an error**; that would return to temporary storage.

## 6. Restore existing accounts BEFORE accepting new registrations

1. Log in to the redeployed site with the existing owner username/password.
2. Open **Admin Panel → Account Data Safety → Import old member backup**.
3. Upload the private SQLite backup from step 1.
4. The cloud import is intentionally allowed only while the PostgreSQL database has **no member accounts**, to prevent overwriting someone else's paid credits.
5. Confirm restored users/credit balances and login using a test member account.
6. Protect the original backup. The new external PostgreSQL database should be backed up via your database provider.

If members have already registered on the new database, do **not** restore an old database on top of their balances. Contact a developer to perform a reviewed merge rather than deleting any user data.

## 7. How the new website works

- Visitors select **Continue with Google** to create an account with verified Gmail. The first successful registration grants the configured welcome balance (default **5 credits**), once per Google account.
- Optional promo codes grant extra credits. A given code can only be used once by each member and stops at its owner-set global limit.
- In **Admin → Promo code generator**, choose bonus credits, maximum uses and expiration; codes can be disabled.
- In **Admin → Credit pack prices**, optionally set NPR prices for 10/25/50/100 credit packs. An unset price remains **Request quote**.
- Members click **Buy Credits**, request a pack and contact the owner. **There is no automatic payment processing**. After confirming actual payment, the owner manually marks the request paid to grant credits.
- The existing invitation-code and username/password logins remain for legacy users.

## 8. Important limitations for selling credits

- A persistent account database is NOT persistent video storage: Render Free may remove uploaded source videos, projects and exported files when it restarts or redeploys. Plan S3/R2 object storage and a job queue before promising long-term project access.
- 100 **registered** users are different from 100 **simultaneous** people exporting videos. Render Free has limited CPU/RAM and ShortMint currently limits concurrent export jobs. For commercial use, budget for an appropriately sized server and a worker/queue.
- Use a proper privacy policy, refund policy, business contact and legally compliant billing before collecting money. `static/privacy.html` is a **draft** that you should tailor.
- Restrict Admin Panel access to your own account; never sell other users' personal information.
- Promote your Google OAuth app to **In production** for a public audience, and complete any verification Google requires.
- Production must be tested against **your actual Google OAuth client and Neon database**, which cannot be done until you configure them.

## Troubleshooting

**Google button says not configured:** Check `GOOGLE_CLIENT_ID` in Render, Authorized JavaScript origins and the browser developer console. 

**New sign-ins cannot save members:** Check `/api/hosting/status`, Neon connection, SSL settings and Neon quota. 

**Old accounts disappeared after migration:** If the new database has no members, use Admin's **Import old member backup**. If any new members exist, do not overwrite them.

**No credits on second sign-in:** Welcome credits are issued only ONCE when an account is first created. You can use a promo code or an owner-approved purchase for more.
