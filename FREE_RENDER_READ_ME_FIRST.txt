ShortMint v3 — Free Render Deployment

1. In GitHub, open your shortmint-studio repository.
2. Open render.yaml -> pencil Edit -> replace its contents with the render.yaml from this ZIP -> Commit changes.
3. On Render, cancel the previous paid Blueprint deployment and create a new Blueprint from the updated repository.
4. Verify that it shows plan: free and NO disk. Never enter payment information solely for this configuration.
5. When asked, provide OWNER_USERNAME and OWNER_PASSWORD as secret environment variables; keep the password private.
6. Deploy and test with a short low-resolution file first (540p, 15 seconds).

IMPORTANT: Render's free instance can sleep and the filesystem is ephemeral. The accounts database, credit balance, invitations and uploaded/exported video files can all be deleted on restart, redeploy or suspension. This is NOT suitable for reliably sharing with friends. Free CPU/RAM and upload/time limits can also break 1080p/large video exports. If Render requests a payment card anyway, stop and review your account and the Blueprint plan; do not assume the deployment is free.

Truly no-cost reliable owner/admin credit history: run on your own PC using start_windows.bat and keep it online for friends on your LAN. Free internet access from your PC can be added using a reputable tunnel service, but uptime, connectivity, and tunnel terms will apply.
