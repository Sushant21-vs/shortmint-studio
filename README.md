# ShortMint Studio login-page contact upgrade

This package contains exactly three replacement files, based on the deployed ShortMint Studio v8.1 source. It preserves the existing login, credit, download, import and admin logic.

## Replace on GitHub

1. Open your repository: https://github.com/Sushant21-vs/shortmint-studio
2. In the `static/` folder, replace `index.html`, `dashboard.js`, and `dashboard.css` with the files inside this ZIP's `static/` folder.
3. Commit all three replacements. Render will redeploy if automatic deploys are enabled.
4. Refresh the login page with Ctrl+Shift+R.

## To make contact links appear

1. Log in as owner and open **Admin Panel**.
2. Find **Free Invite Code — Contact Number**.
3. Save a public Nepal phone number starting with **+977** (example format: `+977 98XXXXXXXX`, not a real number).
4. Sign out or use an incognito tab to check the login page. The box shows a prominent **Call owner** button and **WhatsApp** action, both pointing to that number.

Until you save a number, the page displays an honest placeholder instead of a broken or invented link. WhatsApp chat requires the specified number to have WhatsApp enabled.

The published phone number is visible to everyone visiting the login page. On Render Free, changes saved only to the local SQLite database may be lost on a restart or redeploy because there is no persistent disk; save settings again as needed. For permanent member data, use persistent storage.
