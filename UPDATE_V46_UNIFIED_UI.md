# ShortMint Studio v46 — Unified Creator Workspace UI

## What changed

A unified visual-design layer is applied **across the existing app**: sign-in, dashboard, Create Shorts/editor, credit requests, credit store, order confirmation, private messages, Settings, and owner Admin Panel. This release does not modify the underlying video, billing, account, or messaging endpoints.

- Dark mode: calm navy with orange highlights, clearly readable white/muted-blue text.
- Daylight mode: cool off-white with dark text, not an overbright cream surface.
- Consistent cards, information panels, text fields, buttons, badges, and focus outlines.
- Stronger contrast for uploader, export progress warning, credit requests, and purchase follow-up.
- Better mobile sizing and padding; existing sidebar navigation logic is unchanged.
- Simplified outdated version badges in the workspace UI. The previously approved orange-spark icon stays intact.
- New source stylesheet is **last in the cascade** so older styles do not restore unreadable colors.

## Install from the replacement ZIP

Copy these two files to the corresponding paths in your current GitHub repository:

1. `static/index.html` (links the new stylesheet and updates two decorative badges)
2. `static/shortmint-unified-ui-v46.css` (new visual design layer)

Commit and allow Render to redeploy. Hard-refresh with Ctrl+Shift+R to bypass browser cache.

**Do not delete other CSS files**; the v46 design intentionally overrides the necessary older styles while retaining their layout and interactive behavior. **Do not replace your live database or change environment variables for this UI release.**

## Verification

- Existing backend and frontend-dependent pytest suite: 76 tests passing.
- CSS parsed successfully with zero stylesheet parse errors.
- Verified that page IDs, scripts, forms, and all service integration files were retained.
- Static-page previews were rendered in a local headless Chromium session with styles applied. The dashboard, editor, and inbox were checked at 390px wide with no horizontal page overflow. These are UI previews; authenticated live Render workflows still need checking after deployment.

The full project ZIP intentionally excludes the local `storage/shortmint.sqlite3` database to avoid distributing cached user account data. Keep your current Render database unchanged.

Existing capabilities are unchanged: one account per recorded IP on new registration, invite/promo login, Google-account recovery, video exports up to 1080p, automatic MP4/ZIP downloads, private client messaging, and manual credit order approval.
