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
Don't add a `CNAME` file until the domain is bought; Pages would redirect visitors to a
domain nobody owns. Once Momento has bought it:
1. At the registrar, add DNS records:
   - `A` records for `@`: 185.199.108.153, 185.199.109.153, 185.199.110.153, 185.199.111.153
   - `CNAME` for `www` pointing at `momento-anima.github.io`
2. Add a `CNAME` file containing `theundergroundserver.com`, set `SITE_URL` in
   `build.py`, rebuild, and push.
3. Repo Settings > Pages: set the custom domain, wait for the certificate, and tick
   **Enforce HTTPS**.

Board issue: Momento-Anima/dayz-deer-isle#275.
