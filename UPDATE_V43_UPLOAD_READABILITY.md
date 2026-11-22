# ShortMint Studio v43 — readable upload area

## Fixed
- The **Upload from your device** information strip no longer appears almost white with pale/illegible text.
- Standard dark slate-blue strip with white title, muted light-blue description, peach upload icon and label, suitable for the existing dashboard.
- The actual **drag-and-drop file uploader** also uses high-contrast dark colors, with clearer hover/focus states.
- Works in both app appearance settings and on small screens.

## Deployment
Replace `static/index.html` and add `static/shortmint-upload-contrast-v43.css` in your GitHub repo; commit and let Render redeploy. Then hard-refresh your browser (`Ctrl + Shift + R`). No Python/backend changes.

This is a CSS/text fix; uploading, credits, automatic download, login, and generation logic are untouched.
