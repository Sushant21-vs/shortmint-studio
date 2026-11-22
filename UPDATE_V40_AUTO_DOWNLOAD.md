# ShortMint Studio v40 — Automatic Downloads After Export

Finished exports now request a download automatically when the server marks the task complete:

- **One generated Short:** browser download of that MP4.
- **Two or more Shorts:** single ZIP containing **only the videos generated in this export** (not older clips in the same project).
- **Auto-download is ON by default.** The checkbox below Generate persists the user's preference locally in the browser.
- The results page retains regular manual MP4 downloads and **Download all ZIP**, and now shows **Download MP4/ZIP manually** for the just-completed batch if the browser blocks automatic downloads.
- A job is auto-downloaded only once per page session; reopening a saved project does not automatically download older videos.
- The processing warning remains visible during export.

## Browser notes
A browser may block downloads initiated after background processing, ask for permission, or require the user to allow automatic downloads for this website. The site cannot guarantee the download saved successfully or silently override browser settings. Users can always use the manual download link. Keep the website open until the export is complete.

## GitHub update
Replace `app.py`, `static/app.js`, `static/index.html`, and `static/shortmint-processing-v38.css`. Render should redeploy. No database or environment changes are required for v40.

## Security
The new per-export ZIP endpoint checks authenticated project ownership and only includes whitelisted filenames from the saved project manifest. It rejects malformed task IDs and missing exports.
