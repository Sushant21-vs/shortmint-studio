# ShortMint Studio v34 — 4K/8K Export + Advanced Settings

This is an update from v33. It retains existing Google sign-in, credits, projects, voice choices, settings appearance and prior dashboard changes.

## New video quality options
- 540p — 540 × 960
- 720p — 720 × 1280
- 1080p — 1080 × 1920 (recommended default)
- 4K — **2160 × 3840** (vertical)
- 8K — **4320 × 7680** (vertical)

These are real H.264 vertical MP4 export dimensions. Exporting at a larger resolution **does not increase the real detail of a low-resolution source video**. 4K/8K encoding is CPU-, RAM- and storage-intensive and may be slower than your server can manage.

The app checks available server RAM **before reserving export credits**:
- 4K: requires at least 2048 MB server RAM.
- 8K: requires at least 8192 MB server RAM.

These are basic admission guards, **not performance guarantees**. For sustained 4K/8K production you may need much more RAM, CPU, storage and a longer-running server. High-resolution jobs run exclusively; when an UHD job is running, the next export must wait until it finishes. On small Render instances the UHD options are shown as unavailable and a reason is provided. An attempt to submit UHD on an unsupported server is rejected without deducting credits.

8K MP4 is not compatible with every device or browser video decoder; the download is still available when export succeeds.

## Expanded Settings
- Set default export quality, clip length, number of Shorts, and center/blur/left/right framing.
- Enable or disable default audio normalization.
- Pick one of the existing 6 voices and choose replace or mix audio.
- Enable automatic subtitles as an optional default (cloud transcription may send audio to your provider and incur fees).
- Save settings locally in the browser and apply to the current video editor.
- Reset only editor defaults, with confirmation; cloud projects and credits are not removed.
- Original Appearance, Motion & Effects, Privacy Policy, account info, and Sign out remain available.

Default settings apply only in the current browser/device. The narration itself remains off until the user enables voiceover inside the editor. Existing selected values can still be changed for each Short.

## Deploy update on GitHub / Render
For the **replacement ZIP**, place files in the same relative paths in your existing repository and commit:

- `app.py`
- `static/index.html`
- `static/dashboard.js`
- `static/shortmint-export-v34.js` *(new)*
- `static/shortmint-export-v34.css` *(new)*

If Render is connected to your repository, it will redeploy. If you upload the full ZIP, preserve your own Render **environment variables**, persistent DATABASE_URL, and any secrets. Do not paste the ZIP over server database or media storage. The change does **not** require new paid APIs or packages.

## Checks
- 49 automated Python tests passed (including 3 new UHD/settings tests).
- An actual H.264 MP4 frame was encoded and verified at 2160 × 3840.
- The 8K export path and memory guard were unit-tested; full 8K rendering has **not** been benchmarked on an 8+GB server.
- Browser screenshot verification could not complete in the local restricted Chromium environment.
