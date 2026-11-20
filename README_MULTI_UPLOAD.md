# ShortMint Studio v11 — Multi-video upload

Upload **1–6 videos at once** from Create Shorts → Upload file → Choose multiple videos. Drag-and-drop multiple files is supported. Files upload **sequentially** using the existing `/api/upload` endpoint; after uploads finish, click **Edit Short** beside any video. Each video is stored as a separate project and remains available on the dashboard as long as host storage remains.

## Deploy to your existing ShortMint GitHub repository

Replace `static/index.html` and `static/app.js`; add `static/multi-upload.css`. Commit and wait for Render auto-deploy. Clear browser cache (Ctrl+Shift+R). **No backend changes are required**.

## Constraints

- Maximum 6 selected videos per batch, 1 GiB each; supported MP4/MOV/MKV/WebM/AVI/M4V. If more than six are selected, only the first six are added.
- One HTTP upload request per video, one after another. No multi-video video compositing: **each file becomes a separate editable project**, and exporting Shorts still happens individually.
- The editor opens the first successful upload automatically once the queue finishes. The Edit Short button can switch to other uploaded videos.
- File validation and progress appear for each video. Failed files are marked, and successful ones remain accessible.
- **Render Free does not provide persistent local storage**; uploaded videos/accounts can disappear after restarts or redeploys. Large uploads can fail because of resource/network restrictions. Test smaller MP4s (e.g., 10–50 MB) first.
- Back up all important data before redeploying.
