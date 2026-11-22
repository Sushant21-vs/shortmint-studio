# ShortMint Studio v44 — Orders & Messages

## What was added

- New **Orders & Messages** sidebar page for signed-in clients.
- Clients can open a **Custom video order**, **General question**, or **Account / technical support** conversation, and send follow-up text messages.
- Account-specific private conversations. A member cannot read or modify another member's conversation.
- The owner can access a shared inbox using **Orders & Messages** or **Admin Panel → Orders & direct messages**.
- Owner can reply directly, and set each order's status to **New**, **In progress**, or **Completed**. If a client replies to a completed order, it reopens as New.
- Unread-message counter and an automatic refresh every ~18 seconds while the inbox is open and visible. This is **polling**, not real-time push or email notification.
- Clear, readable navy/slate UI that works on mobile and desktop.
- Enquiries do not charge credits and are not payments or automatic orders for paid services.

## Deploying the replacement ZIP

Extract `ShortMint_v44_Orders_Messages_Replace_Only.zip` and upload its files into **the same relative locations** in your GitHub repo:

```
app.py
accounts.py
pg_storage.py
admin_backup.py
direct_messages.py
static/index.html
static/dashboard.js
static/shortmint-orders-v44.css
static/shortmint-orders-v44.js
static/privacy.html
```

Commit the changes and allow Render to redeploy. Hard-refresh your browser (`Ctrl + Shift + R`) after deployment.

## Persistent database (important)

Conversations are stored in the **account database** and survive browser refreshes. They survive Render server restart/redeploy only when your `DATABASE_URL` points to a durable PostgreSQL database (such as Neon). If ShortMint is still using temporary SQLite storage on Render, messages may be lost on redeploy/restart.

Existing member accounts, credit balances, promo codes, automatic downloads, and 1080p export options remain unchanged. Database schema updates are additive and take place when the service starts. Back up the database before deploying.

Existing owner-only SQLite backups taken **from v44 onwards** include messages, and restoring them remaps conversation accounts and read indicators. Older backups contain no message conversations. In PostgreSQL mode, back up and restore using the PostgreSQL provider.

## Security and usage limits

- All routes require a logged-in session; mutation routes require the application's anti-CSRF request header.
- Owner-only status management and account-scoped thread access.
- New threads capped at 8 per user per 24 hours.
- User messages capped at 30 per hour; message body maximum 2,000 characters.
- No file attachments in this version; text only. Never share passwords or payment details in messages.
- No push/email alerts; the user or owner sees replies in the website inbox when they next open it.

## Tests

`PYTHONPATH=. pytest -q` — **73 tests passed**, including member isolation, owner reply/status control, rate limits, persistence and SQLite backup restoration.

The design was visually inspected as a static local browser preview for desktop and mobile. The end-to-end network browser test couldn't run in this environment because local browser connections are blocked. Test on your live Render site after deploying.
