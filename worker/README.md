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

## CFTools Data API (live players on the admin hub), connected 2026-10-03
- CFTools developer application **"Website"**, application ID `6ac15c4b6e6aa4c19a8df49c`, granted on the Underground
  server (app.cftools.cloud > server > Settings > Webhooks tab lists it under "Third party applications").
  **CFTools cannot limit a grant to read-only**: the app has full access to the marked resource. The Worker only ever
  calls `GET /v1/server/{id}/GSM/list`, and the secret lives only in the Worker. To cut access, remove the app there.
- Worker settings: text `CFTOOLS_APP_ID`, text `CFTOOLS_SERVER_ID` (the "Server API ID" on the server's Settings > API tab),
  secret `CFTOOLS_SECRET`. Route `/admin/players` (admins only) returns name, steam64, ping and position only, never IPs.
- API: `POST https://data.cftools.cloud/v1/auth/register {application_id, secret}` -> token (cached ~20 h);
  sessions carry `live.position.latest = [x, y, z]`. A wrong secret answers `403 bad-secret`, an unknown app id `404 not-found`.
- **Gotcha 1 (cost an hour):** the first CFTOOLS_SECRET held the 24-character application ID, because the secret's Copy
  button did not take and the earlier clipboard content was pasted. A temporary diagnostic showed the stored length (real
  secret is far longer than 24); it has been removed. If login to CFTools ever fails again with `403 bad-secret`, re-copy.
- **Gotcha 2:** CFTools orders positions as **(east, NORTH, height)**, not DayZ's (east, height, north) (see the
  `Coordinates` note in cftools-sdk). `/admin/players` maps `z` = array[1] (north) and `y` = array[2] (height); the first
  version used them the wrong way round and the dots were in the wrong places.
- No reset option exists for the secret in the developer portal. If it is ever lost, create a new application and re-grant.

