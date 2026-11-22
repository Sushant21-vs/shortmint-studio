# ShortMint Studio v45 — Credit order next steps

After any signed-in client submits a credit purchase inquiry, a confirmation panel shows their order number, credit amount, payment-pending status, and the message that payment is confirmed manually before credits are granted. The panel persists on the Buy Credits page while their inquiry remains pending (including after refreshing).

Three optional contact buttons are populated from existing **Admin Panel** settings, not hard-coded addresses:

- **WhatsApp** — Admin → Direct Contact → WhatsApp number (include country code).
- **Gmail / Email** — Admin → Direct Contact → email (or Public Contact email if the first is blank).
- **Instagram** — Admin → Public Contact & Socials → Instagram profile URL or @handle.

The WhatsApp and email templates include the order ID and username; Instagram opens the configured profile. An in-app Orders & Messages button is always available. If no external details are configured, the page says so instead of showing fabricated contacts.

The request does not take payment or automatically add credits. The owner's existing manual payment verification and grant-credit flow remains unchanged. No new environment variables are required.

## GitHub update

Upload the `accounts.py`, `static/dashboard.js`, `static/index.html` and new `static/shortmint-credit-followup-v45.css` in their matching locations. Redeploy on Render, and hard-refresh the page.

This update is based on ShortMint Studio v44 and retains its functionality.
