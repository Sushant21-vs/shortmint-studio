# ShortMint Studio v24 - Cloud Cursor Everywhere

The decorative peach-orange cloud trail now follows the pointer on **every** page: Login, Dashboard, Create Shorts, Credits, and Admin. Clicking/touching creates a small burst. The canvas is fixed with pointer-events:none, so it never catches input, and animation is limited when Reduced Motion is enabled.

## How to update GitHub

1. Replace `static/index.html` in your repository.
2. Add `static/shortmint-cloud-v24.css` and `static/shortmint-cloud-v24.js`.
3. Commit and wait for Render's automatic deployment, then hard refresh (Ctrl+Shift+R).

All video, member, credit, and backup routes are unchanged. The old login-only canvas is removed from HTML to avoid two competing cloud animations; other v21 login/admin code is unchanged.

### Data safety
Render Free stores SQLite and uploaded videos on temporary storage. Download your private admin backup before deploying to avoid losing accounts, invitations, credits and projects after a restart.
