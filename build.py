"""Build the site: src/<page>.html fragments -> <page>/index.html, plus preview/ fragments.

Each src file is a fragment: a <title>, an optional <!-- desc: ... --> line, then the page's
own content (everything inside <main>). Links and assets in fragments are root-relative
(/assets/..., /map/), because the site is served from the domain root. build.py adds the
head, nav, footer and scripts so every page is the same.

preview/<page>.html is the same page without the document skeleton and with flat asset
paths, for the private Claude artifact preview that Momento approves wording on.

    python build.py

Writes UTF-8 without a BOM.
"""
import re
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE_URL = "https://theundergroundserver.com"
DISCORD = "https://discord.gg/tudayz"

# The live server, as DZSA's public list shows it (2026-10-02). Game port is what
# players connect to; the query port is what the status check and the join link use.
SERVER_IP = "74.50.72.74"
GAME_PORT = 2744
QUERY_PORT = 2816

# Fill these in when Momento has the IDs. Empty = the tag is not emitted.
GA_ID = "G-6Y451GF7E2"          # Google Analytics measurement ID, "G-XXXXXXXXXX"
ADSENSE_ID = ""     # AdSense publisher ID, "ca-pub-XXXXXXXXXXXXXXXX"

# Discord login (worker/worker.js, deployed at api.theundergroundserver.com 2026-10-03).
# Turning it off also hides the login paragraph on the privacy page.
LOGIN_ENABLED = True
API_BASE = "https://api.theundergroundserver.com"

# Pages that are built into preview/ only, never deployed, until Momento approves their wording
# (or, for admin.html, until the Worker has its admin role set). Remove a name to go live; add it
# to NAV once it should be linked.
DRAFT_PAGES = set()      # approved 2026-10-03 (unlinked): appeals, admin
# Built and deployed but kept out of search engines until they are linked in NAV.
NOINDEX = {"appeals", "admin", "404"}

# (src stem, nav label). Order = nav order. Pages not listed (privacy) still build.
NAV = [("index", "Home"), ("news", "What's new"), ("notoriety", "Notoriety"), ("map", "Map")]

FONTS = ("https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@600;800"
         "&family=Barlow:ital,wght@0,400;0,600;1,400&family=IBM+Plex+Mono:wght@500&display=swap")


def asset(path):
    """Root-relative URL with a cache-busting query from the file's contents."""
    return f"/{path}?v={zlib.crc32((ROOT / path).read_bytes()):08x}"


def parse(src):
    title = re.search(r"<title>(.*?)</title>", src, re.S).group(1).strip()
    m = re.search(r"<!--\s*desc:\s*(.*?)\s*-->", src, re.S)
    desc = m.group(1).strip() if m else ""
    body = re.sub(r"<title>.*?</title>\s*", "", src, count=1, flags=re.S)
    body = re.sub(r"<!--\s*desc:.*?-->\s*", "", body, count=1, flags=re.S)
    if LOGIN_ENABLED:
        body = body.replace("<!--login-->", "").replace("<!--/login-->", "")
    else:
        body = re.sub(r"<!--login-->.*?<!--/login-->\s*", "", body, flags=re.S)
    return title, desc, body.strip()


def nav_html(stem):
    links = []
    for s, label in NAV:
        href = "/" if s == "index" else f"/{s}/"
        cur = ' aria-current="page"' if s == stem else ""
        links.append(f'<a href="{href}"{cur}>{label}</a>')
    return ('<nav class="nav wrap"><a class="brand" href="/"><img src="/assets/favicon-32.png" '
            'alt="" width="30" height="30">The Underground: Reborn</a>'
            + "".join(links) + f'<a class="discord" href="{DISCORD}">Discord</a>'
            + ('<span class="account" data-account></span>' if LOGIN_ENABLED else '') + '</nav>')


FOOTER = ('<footer class="wrap"><span>The Underground: Reborn &middot; Deer Isle &middot; '
          '<a href="/privacy/">Privacy</a></span>'
          '<span>Not affiliated with Bohemia Interactive. DayZ is a trademark of Bohemia Interactive a.s.</span>'
          '</footer>')


def analytics():
    out = []
    if GA_ID:
        out.append(f'<script async src="https://www.googletagmanager.com/gtag/js?id={GA_ID}"></script>'
                   '<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}'
                   f'gtag("js",new Date());gtag("config","{GA_ID}",{{anonymize_ip:true}});</script>')
    if ADSENSE_ID:
        out.append(f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js'
                   f'?client={ADSENSE_ID}" crossorigin="anonymous"></script>')
    return "\n".join(out)


def build_page(stem):
    title, desc, body = parse((ROOT / "src" / f"{stem}.html").read_text(encoding="utf-8"))
    page_url = SITE_URL + ("/" if stem == "index" else f"/{stem}/")
    config = (f'<script>window.TUR={{ip:"{SERVER_IP}",gamePort:{GAME_PORT},queryPort:{QUERY_PORT},'
              f'discord:"{DISCORD}"' + (f',api:"{API_BASE}"' if LOGIN_ENABLED else '') + '};</script>')
    shared = (f'{nav_html(stem)}\n<main class="wrap">\n{body}\n</main>\n{FOOTER}\n{config}\n'
              f'<script src="{asset("assets/site.js")}" defer></script>')
    robots = '<meta name="robots" content="noindex">' if stem in NOINDEX else ""
    jsonld = ""
    if stem == "index":
        import json as _json
        jsonld = '<script type="application/ld+json">' + _json.dumps({
            "@context": "https://schema.org",
            "@graph": [
                {"@type": "WebSite", "@id": SITE_URL + "/#site", "url": SITE_URL + "/", "name": "The Underground: Reborn",
                 "description": desc, "inLanguage": "en"},
                {"@type": "Organization", "@id": SITE_URL + "/#org", "name": "The Underground: Reborn", "url": SITE_URL + "/",
                 "logo": SITE_URL + "/assets/icon-512.png", "sameAs": [DISCORD]},
            ]}, separators=(",", ":")) + "</script>"
    full_title = title if stem == "index" else f"{title} | The Underground: Reborn"
    head = f"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{full_title}</title>
<meta name="description" content="{desc}">
<meta name="theme-color" content="#0e0c0b">
{robots}
<link rel="canonical" href="{page_url}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="The Underground: Reborn">
<meta property="og:title" content="{full_title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{page_url}">
<meta property="og:image" content="{SITE_URL}/assets/share-card.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" type="image/png" sizes="32x32" href="/assets/favicon-32.png">
<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
<link rel="stylesheet" href="{asset("assets/site.css")}">
{analytics()}
{jsonld}"""
    html = f'<!doctype html>\n<html lang="en">\n<head>\n{head}\n</head>\n<body>\n{shared}\n</body>\n</html>\n'
    out = ROOT / "index.html" if stem == "index" else (ROOT / "404.html" if stem == "404" else ROOT / stem / "index.html")
    if stem not in DRAFT_PAGES:
        out.parent.mkdir(exist_ok=True)
        out.write_bytes(html.encode("utf-8"))
    elif out.exists():
        out.unlink()            # a draft must never linger in the deploy tree
        if out.parent != ROOT and not any(out.parent.iterdir()):
            out.parent.rmdir()

    # Preview fragment: flat asset paths, page links point at the live site.
    preview = re.sub(r'(src|href)="/assets/([^"?]+)(\?[^"]*)?"', r'\1="assets/\2"', shared)
    preview = re.sub(r'href="/([a-z]*/?)"', rf'href="{SITE_URL}/\1"', preview)
    preview = (f'<title>{title}</title>\n<link rel="stylesheet" href="{FONTS}">\n'
               f'<link rel="stylesheet" href="assets/site.css">\n{preview}')
    (ROOT / "preview").mkdir(exist_ok=True)
    (ROOT / "preview" / f"{stem}.html").write_bytes(preview.encode("utf-8"))
    return out


def write_seo_files():
    """sitemap.xml (indexable pages only), robots.txt. Pages in NOINDEX are left out."""
    import datetime
    today = datetime.date.today().isoformat()
    stems = [f.stem for f in sorted((ROOT / "src").glob("*.html"))
             if f.stem not in NOINDEX and f.stem not in DRAFT_PAGES and f.stem != "404"]
    order = [s for s, _ in NAV] + [s for s in stems if s not in [n for n, _ in NAV]]
    urls = "".join(
        f"  <url><loc>{SITE_URL}{'/' if s == 'index' else '/' + s + '/'}</loc><lastmod>{today}</lastmod></url>\n"
        for s in order if s in stems)
    (ROOT / "sitemap.xml").write_bytes(
        ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
         + urls + "</urlset>\n").encode("utf-8"))
    (ROOT / "robots.txt").write_bytes(f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}/sitemap.xml\n".encode("utf-8"))
    print("wrote sitemap.xml (%d urls) and robots.txt" % urls.count("<url>"))


def main():
    write_seo_files()
    for f in sorted((ROOT / "src").glob("*.html")):
        out = build_page(f.stem)
        print(("draft (preview only) " if f.stem in DRAFT_PAGES else "wrote ") + str(out.relative_to(ROOT)))


if __name__ == "__main__":
    main()
