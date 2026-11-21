# ShortMint Studio v35 — Remove 8K quality

This update removes 8K from both the Short editor and the Settings default-quality selector, while retaining 4K (2160 × 3840), 1080p, 720p and 540p. The server now rejects attempts to request the former 8K setting. All other features introduced through v34 remain.

## Update your current GitHub repository
Extract the **Replace Only** ZIP and upload files to their matching paths:

- `app.py`
- `static/index.html`
- `static/shortmint-export-v34.js`

The updated JavaScript gets a new cache version to take effect after Render redeploys. Any previously saved 8K default will fall back to 1080p because 8K is no longer a valid option. 4K still needs at least 2 GB RAM on the server; this is a basic limit, not a performance guarantee.

No API keys, database changes, or new dependencies are required.
