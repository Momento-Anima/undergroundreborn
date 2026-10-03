# Discord login Worker

`worker.js` is deployed by hand in the Cloudflare dashboard (no Node or wrangler on this PC):
Workers & Pages > `divine-brook-b969tur-login` (Cloudflare added the random prefix) > Edit code >
paste `worker.js` > Deploy.

**To change it:** edit `worker.js` here, commit, then paste and Deploy again. The dashboard copy
is the live one; this file is the source of truth.

## Setup (done 2026-10-03)
- Discord application "The Underground: Reborn", Client ID `1555848080866283550`, redirect
  `https://api.theundergroundserver.com/callback`. Scopes: identify, guilds.
- Address: proxied `AAAA api -> 100::` record in Cloudflare DNS + a Workers Route
  `api.theundergroundserver.com/*` to this Worker. The Worker's "custom domain" screen refused
  ("No zones match"), the route works. This is the only orange-cloud record; the GitHub Pages
  records must stay grey.
- Worker settings (Settings > Variables and secrets): text `CLIENT_ID`, `GUILD_ID`; secrets
  `CLIENT_SECRET` (reset 2026-10-03 and pasted straight from Discord), `SESSION_SECRET`.
  **Never put these in chat, the repo, or a screenshot.** To rotate the Client Secret, reset it
  in the Discord developer page and paste the new one into Cloudflare.
- Site side: `LOGIN_ENABLED = True` in `build.py`; the login paragraph on the privacy page appears
  only when it is on.

## What it holds
Nothing is stored server-side. The cookie (7 days) carries Discord ID, display name, avatar and
"is in our server". Phase 2 (personal stats) and 3 (staff tools) are planned in issue #285.
