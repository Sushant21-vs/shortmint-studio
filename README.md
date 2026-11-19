# ShortMint Studio v5 — Social Link Shorts + Free Daily Video Downloads

This upgrade extends ShortMint Studio v4 (manual Buy Credits, owner approvals, and the **Made by Sushant Hero** footer). It retains the free Render Blueprint and all existing functionality.

## New features in v5

**Create Shorts from links:** In **Create Shorts → YouTube / TikTok / Instagram link**, paste a public HTTPS video URL that you own or have permission to edit. ShortMint imports it through yt-dlp and opens the usual trimming, captions, vertical crop and MP4 editor. Import itself does not deduct any Shorts credits; exporting Shorts still consumes the existing member balance (1 per Short). Many Instagram/TikTok links may block automated extraction, require login, or restrict quality. The website does not bypass these restrictions.

**Separate Download Videos tab:** Paste a YouTube, TikTok or Instagram public video URL, select a quality, check the permission confirmation, and start the download. Files are private to the signed-in user. Video downloads are source files, **not** necessarily MP4 or already formatted as vertical Shorts. Download files expire after 6 hours on the server.

**Free daily download credits (independent of the Shorts/buy credits):**

| Quality selected | Free daily download credits used |
|---|---:|
| 720p | 1 |
| 1080p | 1 |
| 1440p / 2K | 2 |
| 2160p / 4K | **3** |

- Friends receive a default allowance of **5 free download credits per UTC day**, renewing at 00:00 UTC. This is a *spending limit*, not a credit balance added to their regular Shorts credits. The default allows five HD downloads, or one 4K plus two HD downloads, provided the files are available.
- The owner has unlimited download credits. **Admin panel → New Member Settings → Free download credits per member / day** can adjust the allowance from 0 to 100. The cap is enforced transactionally by the server; users cannot edit their balances in the browser.
- A successful download uses the selected quality's daily credits even if the source offers only a lower quality for 720p/1080p. **1440p/4K are required to be available**; otherwise the operation fails and returns the reserved credits. Failed downloads also return their credits.
- The extractor uses yt-dlp to access public accessible media only, with **no login cookies, DRM bypass, or private-content access**. Some platform links may not work because of platform restrictions, rate limits, or extractor changes. 4K is rare on TikTok and Instagram.
- Download size is limited to about 350 MB per file and processing time is limited to 10 minutes. Render Free may fail much earlier due to limited CPU/RAM/storage; testing at 720p with small clips first is recommended.
- Download files are kept in an authenticated temporary folder and pruned after 6 hours as new downloads occur. Their daily allowance record remains in SQLite for the day. Requesting a saved file again does not use another credit while it is available.

## Files to replace in existing GitHub repository

Upload these files **preserving the indicated paths** to the root of `Sushant21-vs/shortmint-studio`:

```text
app.py                        REPLACE
accounts.py                   REPLACE
downloads.py                  ADD (new backend)
static/index.html             REPLACE
static/dashboard.js           REPLACE
static/downloads.js           ADD (new page interactions)
static/downloads.css          ADD (new page styling)
README.md                     REPLACE (optional documentation)
```

No change needed to `render.yaml`, `Dockerfile`, or the existing credits/shorts files. Commit changes to `main` and Render should redeploy the site (Settings → Deploys for status). **The existing Render Free server is ephemeral**: a redeploy, restart or spin-down can delete the SQLite database of members, credits, invite codes, purchase requests and video files. No site with paid credits should take real customer money without a durable database, storage and backups. This does not become persistent merely because it is on GitHub.

Run locally: extract the complete v5 archive and run `start_windows.bat` (FFmpeg + Python needed). Run automated tests with `python -m pytest -q tests/` after installing `pip install -r requirements.txt pytest httpx`. The tests verify daily quotas and download delivery with **mocked social-platform retrieval**. They do **not** prove that every live YouTube, TikTok or Instagram URL will be downloadable on Render.

---

## Previous v4 documentation

## NEW v4: Buy Credits / Contact Owner (manual payments, free to use)

- Friends can visit **Buy Credits** and choose 10, 25, 50, 100, or a custom number of credits. **No prices or payment gateways are promised or displayed.**
- They leave an email or WhatsApp number and submit an inquiry; this appears in the **owner's Admin Panel → Purchase Inquiries**. A user can have one pending inquiry at a time.
- Owner can optionally enter a WhatsApp number and/or contact email in **Admin Panel → How members can contact you**. Signed-in members get direct WhatsApp/email links as well as the in-app request form. Leave fields blank for in-app inquiries only.
- **No credits are granted when someone clicks Buy or sends a request.** Only the owner can click **Mark paid & grant**, after independently verifying payment. The grant and review status are applied atomically, with a credit audit trail, and the same order cannot be fulfilled twice.
- Credits can also be granted or removed directly in **Admin Panel → Member Accounts**. Set **Starting credits per friend** to `0` if you want every new friend to receive credits only from you. Previously registered members keep their existing balances.
- This update uses the existing SQLite database and creates a new table. On a persistent installation, existing accounts, invitations, credit balances and projects remain intact. **Back up your database before replacing code.**
- The included browser-tab/favicon update is preserved.
- **Free Render limitation:** SQLite data, members and video files can be lost when the instance restarts, sleeps or is redeployed. This is not suitable for storing paid customer credit balances. Use a persistent DB/storage setup before accepting real money.

### Upgrade your existing GitHub repository

Replace these five files **at the same paths**, do not delete your existing repository:

1. `accounts.py`
2. `static/index.html`
3. `static/dashboard.js`
4. `static/dashboard.css`
5. `README.md` (optional documentation update)

Your existing `app.py`, `render.yaml`, `Dockerfile`, and all other files do not need changes. Once committed, Render should redeploy automatically. On the **free tier**, redeployment may reset the existing accounts and credits.

---

# ShortMint Studio v4 — Manual Buy Credits + Owner-Only Grants

A real video-to-Shorts editor with private accounts, an orange-on-dark dashboard, friend invitations and a server-enforced credit system. **Ready to put in a GitHub repository**, with a Dockerfile and Render Blueprint for a running website. The ZIP contains source code — it is not an already hosted live service.

## What you can do

- Upload a video (MP4/MOV/MKV/WebM/AVI/M4V, max 1 GB) or try importing your own video via a YouTube URL (YouTube sometimes blocks automated imports).
- **Smart picks**: multiple audio-activity-based highlights; this is NOT guaranteed viral-scene AI detection.
- **Custom clip**: choose any start and length (15–180 seconds); smart picks support 1–8 Shorts at once.
- Export **9:16 portrait, H.264 / AAC MP4 at 30 fps**, 540 × 960, 720 × 1280, or **1080 × 1920**. 1080p is recommended for final YouTube uploads if your server is powerful enough.
- Center crop with adjustable horizontal subject focus, left/right crop, or blurred vertical background.
- Add a headline, optional **@channel watermark**, normalize spoken audio, and burn captions into the video.
- **SRT captions**: paste subtitles or upload an `.srt` file; use ORIGINAL VIDEO timestamps (not clip-relative), and each exported segment will get the matching words. SRT subtitles are fully functional without third-party services.
- **Optional automatic speech-to-text**: install the separate `requirements-auto-captions.txt` / build Docker with `WITH_AUTO_CAPTIONS=1` (see below). By default, it is *not installed* because it downloads a speech model and needs significant CPU/RAM. Review the transcript before exporting; no automatic transcription accuracy guarantee.
- Preview and download finished clips individually or as a ZIP. Copy a suggested title and open YouTube Studio to upload **manually**. Automatic YouTube publishing/OAuth is not implemented.
- Private owner account has **unlimited credits**. Friends join via single-use invitations, begin with 5 credits, spend **1 credit per finished Short**, and request more from your admin panel. Failed/cancelled exports refund credits. Admin can approve requests, grant credits, and disable accounts. The server—not the browser—enforces this.

**YouTube Shorts:** videos with a vertical or square aspect ratio and up to 3 minutes qualify for Shorts under YouTube's current guidance. This editor deliberately uses vertical 9:16 and at most 180-second clips. Copyright, upload limits and other YouTube requirements still apply.

## 1. Run on your Windows PC first (no cloud cost)

1. Install Python 3.11+ and FFmpeg (`winget install Gyan.FFmpeg`). Your FFmpeg 9.0.2 installation already works.
2. Extract this ZIP, open `ShortMint_Studio_v3`, and double-click **`start_windows.bat`**. Close any earlier ShortMint server on port 8765 first.
3. On first run, the terminal will prompt for your private owner username and a password of at least 10 characters.
4. Open **http://127.0.0.1:8765**. Log in, upload a small video, try **Custom clip → 15 seconds → 540p** first, then download the MP4.
5. For automatic captions on Windows, open Command Prompt in the app folder after the first launch and run `.venv\Scripts\python.exe -m pip install -r requirements-auto-captions.txt`. Restart the app. It downloads a model the first time you click **Auto-transcribe**.

The Windows launcher, account database and your videos stay on your computer. Back up `storage/` regularly (stop the server first). The new ZIP does not include your previous v2 accounts/videos: copy your old `storage/` into this version **before starting the new site**, after making a backup. If installing new, no data migration is necessary.

## 2. Upload the project to GitHub

**DO NOT select GitHub Pages**; that only hosts static HTML/CSS/JS and cannot execute Python/FFmpeg. This application needs a backend server.

1. Go to https://github.com/new and create a repository, for example `shortmint-studio` (prefer **Private**).
2. Unzip the package, open the `ShortMint_Studio_v3` folder, and **upload the contents** of that folder into the repository root. GitHub's **Add file → Upload files** allows multiple selected files, but uploading nested directories by browser can vary. Ensure the root contains `Dockerfile`, `render.yaml`, `app.py`, `accounts.py`, `captions.py`, `static/`, and `requirements.txt`.
3. Commit the files to the `main` branch. **Never upload `.env`, `storage/shortmint.sqlite3`, videos, password files, or personal data**. The `.gitignore` and `.dockerignore` already exclude common sensitive data. Confirm no stored credentials are present before making a repo public.
4. GitHub Actions will execute a short conversion test automatically (`.github/workflows/test.yml`) when included in the repo.

## 3. Put your GitHub repository online with Render (supports FFmpeg)

1. Sign up at https://render.com and connect the GitHub repository.
2. Choose **New → Blueprint**, choose your repo, and let it find `render.yaml`.
3. In the Blueprint deployment form enter these **secret environment variables** when asked:
   - `OWNER_USERNAME` — your desired admin login (3–24 lowercase letters/numbers/underscore, beginning with a letter)
   - `OWNER_PASSWORD` — a unique password with at least 10 characters; **do not commit it to GitHub**
4. Review the service and persistent-disk costs **before clicking Deploy**. The included Blueprint uses **1 CPU / 2 GB RAM**, plus a **10 GB persistent disk** so the accounts, credits and files survive restarts. This is paid hosting (check the live Render price page).
5. Deploy and wait for the build to finish. Your public link will be similar to `https://shortmint-studio.onrender.com`, with the exact name assigned by Render. Open it and sign in with your owner credentials.
6. Go to **Admin panel → Generate Invite Code**. Share your public website URL and a separate invitation code with each friend.

On a basic shared server, **1080p and long/high-bitrate uploads may be slow or fail due to CPU/RAM/disk quotas**. Try 540p/720p and short source files first; upgrade your instance to handle more users simultaneously. This package uses a single web process with at most two concurrent exports. It is a small private-team implementation, not an unlimited commercial video-rendering platform.

### Optional automatic speech captions on a cloud host

The included Docker image supports SRT subtitles, but *does not include* the speech model by default. To add auto transcription:

- In your Dockerfile change `ARG WITH_AUTO_CAPTIONS=0` to `ARG WITH_AUTO_CAPTIONS=1` and commit. It will install `faster-whisper` during build.
- Choose a hosting plan with enough RAM/CPU. The speech model downloads on first run and automatic speech recognition can be slow or limited by network access. If unsupported, upload or paste SRT captions instead.

### Important cloud limitations

- This is a real backend website; **GitHub Pages alone will not run it**.
- Friends can use the live site only after you deploy and share your actual hosted URL.
- The Render Blueprint has a paid compute plan and disk. **Render's free stateless tier is not appropriate for account/credit/video persistence**.
- YouTube imports may fail due to video restrictions; direct file upload is more dependable. Only download/re-edit videos you own or have permission to use.
- YouTube uploads are **manual**: download MP4, go to https://studio.youtube.com → Create → Upload videos. No Google OAuth integration is included.
- The editor does not guarantee viral clips, automatic face tracking, perfect speech recognition or music copyright clearance. No monthly billing or payment system is included.
- `SHORTMINT_STORAGE_DIR` controls the persistent account + video directory. If changing its path between versions without migration, data will appear missing.
- Hosting providers may impose their own request size/timeout limits. Use their logs if large uploads fail.

## Developer quick commands

```bash
python -m pip install -r requirements.txt
python setup_owner.py   # Only once locally
python launch.py        # Localhost 127.0.0.1:8765
python -m pytest -q tests/   # Install pytest and httpx for tests
```

Docker example, with persistent data and a securely stored password:

```bash
docker build -t shortmint-studio .
docker run -p 10000:10000 -v shortmint-data:/app/storage-data \
  -e OWNER_USERNAME=your_admin -e OWNER_PASSWORD='CHANGE_THIS_TO_A_SECRET' shortmint-studio
```

Security: HTTP-only session cookies; same-origin request headers; passwords hashed with PBKDF2; owner/member roles checked server-side; per-user project isolation; single-use invite codes; persistent SQLite credit ledger. For serious public launch add monitoring, backup automation, rate limits for video uploads, storage quotas, malware scanning, authentication recovery, payment validation if monetized, and a worker queue. No external hosting has been launched or tested with this package.
