# ShortMint Studio v38 — Clean Editor + Processing Reminder

## What changed
- Removed the entire optional Voice Studio panel from Create Shorts (script box, six voices, preview, and narration toggle).
- Removed unused AI voice and voice-mixing defaults from Settings; retained automatic subtitle defaults and audio normalization.
- Retained the existing Speech → Text and auto-caption features in the editor.
- Added a visible warning in the export progress panel: **Recommended not to leave this site during processing.**
- Added a leave-page confirmation while an export is being prepared (including auto-captioning) or while an export job is active.
- Retained 540p, 720p, and 1080p export options, the v37 orange sparkle logo, and the cinematic dashboard design.

## How to apply replacement ZIP
1. Extract the ZIP file.
2. Open your GitHub repository and upload each file to its *matching relative path*, keeping the `static/` folder structure.
3. Commit the changes and let Render redeploy.
4. Hard-refresh your site (Ctrl+Shift+R), open Create Shorts, and check the new processing notice after starting an export.

Changed files:
- `static/index.html`
- `static/app.js`
- `static/shortmint-export-v34.js`
- `static/shortmint-processing-v38.css` (new)

The older `static/voice-studio-v33.js` and `static/voice-studio-v33.css` files are no longer referenced and can be deleted if present. This replacement ZIP intentionally does not alter any backend routes or account data.
