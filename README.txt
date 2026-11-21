# ShortMint Studio v18 — Upload-only source

The YouTube, TikTok and Instagram direct-link import controls have been removed from Create Shorts. Upload video files directly from your device; no YouTube login or automated download is needed.

## Changes
- Upload up to 20 video files per batch, sequentially, with progress and retry.
- File picker no longer filters to only six extensions.
- Server accepts any filename extension but checks the actual media with FFprobe, refusing invalid media and text misidentified as terminal recordings. Actual support depends on the codecs enabled in FFmpeg.
- Common containers include MP4, MOV, MKV, AVI, WebM, WMV, FLV, MPEG, 3GP, M2TS, TS and VOB. Very unusual formats or damaged files may fail.
- Maximum file size remains 1 GiB, free hosting may have tighter practical limits.
- Browser preview availability varies by format; MP4/H.264 is the most compatible.
- All existing Shorts montage editing, credits and account features remain.

## GitHub deploy
Replace these files in the same paths:
- `static/index.html`
- `static/app.js`
- `static/dashboard.js`
- `static/spacious.css`
- `app.py`

Commit to main, wait for Render to deploy, then hard-refresh your browser.

Note: The legacy backend `/api/import-url` remains in this codebase for compatibility but there is no import link or option in the website UI.
Free Render hosting has ephemeral storage; deploys and restarts may lose accounts, saved credits and uploaded videos.
