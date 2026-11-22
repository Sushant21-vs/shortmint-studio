# ShortMint Studio v41 — Existing Google Account Migration

**Latest update:** [UPDATE_V41_GOOGLE_ACCOUNT_MIGRATION.md](UPDATE_V41_GOOGLE_ACCOUNT_MIGRATION.md). Previous Google-only users can verify their saved email and set a local password, without losing the original account/credits. Email sending requires Resend and three secure Render environment variables. Google login remains disabled.

---

# ShortMint Studio v40 — Automatic Downloads

**Latest:** see [UPDATE_V40_AUTO_DOWNLOAD.md](UPDATE_V40_AUTO_DOWNLOAD.md).

# ShortMint Studio v39 — Promo/Invite Registration + IP Signup Guard

**Start here:** [UPDATE_V39_CODE_ONLY_LOGIN_AND_IP_GUARD.md](UPDATE_V39_CODE_ONLY_LOGIN_AND_IP_GUARD.md)

Google sign-in is disabled; new creators register with a single-use invite or an owner-issued promo code plus a username and password. One **new** member can register per recorded public IP. This does not retroactively restrict existing members, and cannot guarantee a unique human. For hosted deployment, preserve `DATABASE_URL` for users and credits. Existing Google-only accounts require a migration plan before sign-out; do not create replacement accounts expecting automatic credit/project transfer.

---

# ShortMint Studio v33 — Speech-to-Text & Six-Voice Narration

**New:** optional automatic video captions plus 3 female and 3 male voiceover styles with audio preview, MP3 download, and narrated MP4 export. See [`UPDATE_V33_SPEECH_TO_TEXT_AND_6_VOICES.md`](UPDATE_V33_SPEECH_TO_TEXT_AND_6_VOICES.md) for setup, privacy and deployment requirements.

---

# ShortMint Studio v27 — Google Accounts, Promo Credits & Cloud Database

**START HERE:** [SETUP_V27_GOOGLE_NEON.md](SETUP_V27_GOOGLE_NEON.md)

This release adds verified Google sign-in (5 welcome credits by default), server-enforced promo codes, owner-defined NPR pack prices, and an external PostgreSQL option for persistent user accounts and credit ledgers. You must configure `DATABASE_URL` and `GOOGLE_CLIENT_ID` in Render before deploying to production. Do not upload secrets or private backups to GitHub. Uploaded videos remain temporary on Render Free.

---

# ShortMint Studio v15 — Open Canvas UI

**Spacious visual redesign for the 20-video upload and multi-cut Shorts editor.**

Start with [README_V15_UI.md](README_V15_UI.md) for the GitHub upgrade instructions and design overview.

---

# ShortMint Studio v14 — Creator Studio

The **Download Videos** page has been removed from the website UI. Create Shorts and download your finished exports as before.

See `README_V14_REMOVE_DOWNLOADER.md` for update instructions. Earlier version notes in this repository are historical.


## v16 clean login update
See `README_V16_CLEAN_LOGIN.md`.

## Latest update — v36
The Shorts editor maximum export quality is 1080p. 4K and 8K have been removed from the editor, Settings and backend. See UPDATE_V36_MAX_1080P.md.
