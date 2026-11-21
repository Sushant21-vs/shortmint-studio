# ShortMint Studio v17 — Creator Portal Login

Replaces the previous plain white login screen with a premium, centered login experience: dark studio backdrop, subtle film motifs, refined white card, interactive tabs, inputs with icons, animated sign-in button, show/hide password, and invite-contact panel. The workspace, Shorts creator, credit balance, admin functions, and upload queue are unchanged.

## GitHub upgrade

Replace `static/index.html`. Add `static/login-atelier.css` and `static/login-atelier.js`. The older `static/login-clean.css` is no longer loaded (you may remove it later). Commit the changes and allow Render to redeploy. Hard refresh with Ctrl+Shift+R if necessary. No new Python requirements or external frameworks.

## Testing and notes

This is a visual login-page update only; it does not change backend security or restore data on Render Free. Keep account/password secrets out of GitHub. The invite contact links still display only if configured by the owner in Admin. The new show-password button is local-only. The decorative animations are disabled with reduced-motion preferences.
