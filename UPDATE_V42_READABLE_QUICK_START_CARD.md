# ShortMint v42 — readable quick-start card

The dashboard Quick Start card now uses a standard dark-slate color with white heading, readable description, high-contrast orange button, and a warning that video files and unsaved edits may be lost after refreshing/leaving the page.

This is a visual and content-only update. It does not change video storage behavior. Server exports may remain linked to projects and stored files depend on Render's ephemeral/persistent storage. For that reason the warning uses “may be lost”, rather than incorrectly guaranteeing deletion at refresh.

## Replace-only instructions

1. In your GitHub repository, replace `static/index.html`.
2. Add `static/shortmint-readable-card-v42.css`.
3. Commit changes and allow Render to redeploy.
4. Hard-refresh with Ctrl + Shift + R.

Test both light and dark appearance modes and mobile widths. Existing features and API routes unchanged.
