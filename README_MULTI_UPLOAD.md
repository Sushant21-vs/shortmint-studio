# ShortMint Studio v12 — 20 Video Batch Upload

This update upgrades the existing ShortMint Studio video workspace from **6 to 20 videos in one batch**. Source videos are processed **one after another**, to reduce overload on a small server. Individual rows show upload progress and errors. Use **Edit Short** on any finished project and **Retry failed** to retry individual network/server failures.

## Create Shorts source choices
- **Upload file:** drag-and-drop or browse up to 20 MP4/MOV/MKV/WebM/AVI/M4V files (server enforces max 1 GiB per file).
- **YouTube:** optional URL import remains, but automated downloads from Render may be restricted by YouTube. An inaccessible link cannot be made reliable solely by changing the interface; use Upload file when blocked.
- **TikTok and Instagram:** direct URL tabs were **removed from Create Shorts** because cloud extraction cannot be guaranteed. Import an MP4/MOV file that you have permission to use. The *separate* Download Videos page remains unchanged and may support accessible links.

Uploads create twenty **separate projects**, not one combined video. Your normal Short generation credits, admin, login, and downloader are unchanged.

## Deploy on GitHub
Replace **static/index.html**, **static/app.js**, **static/source-studio.css**, and **static/multi-upload.css** with the contents of `ShortMint_v12_Replace_Only.zip`. Commit to the main branch and allow Render to redeploy. Refresh your browser with Ctrl+Shift+R. The whole project is in `ShortMint_Studio_v12_Full_GitHub.zip`.

## Limits and risks
- Rendering and upload speed are bounded by your server, network, video duration, and storage. Twenty files are queued, **not uploaded simultaneously**; twenty large files may exceed Render Free disk/memory or time out. Start with small videos (~10–50 MB each).
- Free Render storage is **not persistent**: accounts, credits, files, and projects may disappear after restarts/redeployments; back up important data before updating and do not rely on it for paid credit balances.
- There is no automatic joining of multiple source files into one video.
- Test live source imports in your own environment. YouTube, TikTok, and Instagram can restrict automated downloads independent of ShortMint.
