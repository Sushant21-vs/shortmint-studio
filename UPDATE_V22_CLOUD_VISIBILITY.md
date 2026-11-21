# ShortMint Studio — Cloud Cursor Visibility Fix (v22)

Only the login animation is changed; login, dashboard, video editing, credits and storage are unchanged.

## Replace on GitHub

1. `static/index.html`
2. `static/creator-experience-v21.css`
3. `static/creator-experience-v21.js`

Commit, allow Render to redeploy, then press Ctrl+Shift+R to bypass browser cache.
Move the mouse around the **login page**: peach cloud puffs should follow it. Touching shows a small cloud burst. The cloud is only enabled on login, not on the signed-in dashboard.

If Reduced Motion is enabled on your device, moving cloud effects are minimized in respect of accessibility settings.

This update does not fix Render Free's temporary storage. Back up accounts and credits before redeploying.
