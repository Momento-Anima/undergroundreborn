# The Underground: Reborn: website

The public one-page site for the TUR DayZ server (Deer Isle), hosted on GitHub Pages.

**This repo is public.** Put nothing in it from the server: no configs, webhooks, tokens,
IPs/ports Momento hasn't approved, or Steam64 IDs. Every player-facing word needs
Momento's approval before it's pushed.

## Files
- `page.html`: the source. Edit this one.
- `build.py`: wraps `page.html` into a full `index.html` (meta tags, icons, share card).
  Run `python build.py` after every edit, then commit both files.
- `assets/`: logo and icons, from `G:\TUR\TUR_logos\` (`tur_full_logo_v6_transparent.png`
  and `underground_reborn_fire_logo_transparent.png`).
- `.nojekyll`: serve the files as-is.

## Domain: theundergroundserver.com
**Connected 2026-10-02.** Momento bought it at **Cloudflare** (registered 2026-10-03 UTC,
expires 2027-10-03). The domain lapsed once before, so keep auto-renew on. HTTPS is
enforced, and `www` and `http` redirect to `https://theundergroundserver.com`.

For the record, this is how it was set up:
1. Cloudflare DNS records, all **DNS only** (grey cloud, so GitHub can issue the certificate):
   - `A` records for `@`: 185.199.108.153, 185.199.109.153, 185.199.110.153, 185.199.111.153
   - `CNAME` for `www` pointing at `momento-anima.github.io`
2. Add a `CNAME` file containing `theundergroundserver.com`, set `SITE_URL` in
   `build.py`, rebuild, and push.
3. Repo Settings > Pages: set the custom domain, wait for the certificate, and tick
   **Enforce HTTPS**.

**Gotcha:** if the custom domain is set *before* the DNS records exist, GitHub never
requests a certificate (`https_certificate` is missing from the Pages API). To fix it,
clear the custom domain and set it again once DNS resolves. The certificate was then
approved within about a minute.

Board issue: Momento-Anima/dayz-deer-isle#275.
