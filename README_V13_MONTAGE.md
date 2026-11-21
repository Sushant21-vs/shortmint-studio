# ShortMint Studio v13 — Edited Montage Mode

**This update changes the result, not just the interface.** In v12, "Smart picks" exported one continuous 15–180-second excerpt. In v13, **Auto Montage** assembles one Short from **2–12 non-adjacent video sections**, using FFmpeg scene changes and audio silence/activity heuristics, optionally adding alternating punch-in zoom for visual emphasis.

## What is new

- **Auto Montage (now default):** make real jump-cut edits across several parts of a source video. Available cut pacing: **Fast** (~2–4s shots), **Balanced** (~4–6s) and **Story** (~6–9s). Scene-boundary and silence awareness is heuristic, not semantic AI understanding.
- **My Cut List:** create a deliberate edit by entering 2–12 source ranges, one per line, e.g. `00:02-00:05`, `00:12-00:16`, `00:23-00:28`. The website joins those exact parts into one finished MP4, in your chosen order.
- **Classic excerpt:** keep the old audio-activity-based single-interval suggestions for users who want a continuous passage.
- **Single cut:** keep the manual start-time editor.
- **Cut breakdown:** click **View source cuts** under an exported montage to inspect the exact source timestamps for each shot.
- Existing titles, watermarks, subtitles, 9:16 rendering, MP4 download, the owner/admin credit system, buy credits, download videos and **20-video sequential upload queue** remain.

## Update your existing GitHub + Render site

Use `ShortMint_v13_Montage_Replace_Only.zip` (the FULL ZIP is for fresh installations). Preserve the folder structure.

- **Replace** root `app.py`
- **Add** root `montage.py`
- **Replace** `static/index.html`
- **Replace** `static/app.js`
- **Add** `static/montage.css`

Commit the changes in your `shortmint-studio` GitHub repository. If auto-deploy is enabled, Render should redeploy. After Live, refresh using Ctrl+Shift+R. No new Python libraries are required: this feature uses your existing FFmpeg installation and Python standard library.

**Important for Render Free:** redeployment can erase account, credit, contact, video and project data because its disk is temporary. Make backups before deploying. Heavy video editing can be slow or fail due to memory/CPU constraints. Start with a 15–30-second sample at 540p.

## How to produce edited Shorts

1. Sign in → **Create Shorts → Upload file** and upload footage; use the existing 20-video batch queue if needed.
2. Open the uploaded video using **Edit Short**.
3. Select **Auto Montage**, choose desired Short length, Fast/Balanced/Story pacing, and optionally leave **Subtle punch-in zoom** enabled. Start with **1 Short / 540p**.
4. Set 9:16 crop, text, channel watermark, and optional SRT captions (or auto-transcribe where speech recognition has been installed on the host). Click **Generate**.
5. Preview the finished stitched result. Expand **View source cuts** to see the edit list, then download the MP4 for posting to YouTube Shorts.
6. If you want precise storytelling, choose **My Cut List** instead and enter your chosen original timestamps; it will produce one video with actual scene changes.

## Real limits / honest description

- This is a **real automatic multi-cut montage**, not a semantic generative AI video editor. It does not identify jokes, contextual hooks, faces or viral moments from video meaning, produce AI voiceover, license third-party footage, or invent B-roll footage.
- A very short, static, or silent source can only yield different crops or sections of the available footage; no algorithm can discover highlights that aren't present. For meaningful results, record longer source videos with multiple useful moments and review the output.
- Some output is shorter than requested, intentionally, to skip unused footage rather than duplicate scenes.
- Subtitles are optional: existing SRT captions are trimmed and burned into each beat independently, preserving speech timestamps. Automatic speech transcription requires the optional host dependency from the existing documentation.
- Your hosting remains the performance bottleneck. Montages require several renders followed by one fast concat; Render Free cannot guarantee speed or permanence.
- Do not confuse this website with direct video downloads from YouTube/TikTok/Instagram. Those imports can be blocked by third-party platforms; directly uploaded video files are most reliable.

## Testing

- Existing 25 back-end tests pass, plus 2 new montage tests.
- Tested production encoding by assembling **8 separate segments** of the user-supplied 30-second example into one vertical MP4 with playable H.264 and AAC streams.
- Browser preview navigation could not be verified here due to the browser runner blocking local development pages. JavaScript syntax and HTML presence checks pass.
