"""Build index.html for GitHub Pages from page.html.

page.html is the editable source. It starts with <title>, font links and <style>, then
the page body. That fragment form is what the Claude artifact preview takes, so the same
file serves both the private preview and the public site.

    python build.py                      # site URL = SITE_URL below
    python build.py https://example.com  # override (used for share-card image links)

Writes UTF-8 without a BOM.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Change to https://theundergroundserver.com once the domain is bought AND the CNAME
# file is added. Until then the site lives at the github.io address.
SITE_URL = "https://momento-anima.github.io/undergroundreborn"

DESCRIPTION = ("A DayZ server on Deer Isle. PvE across the island, PvP zones when you "
               "want a fight, and a story that unfolds the longer you survive.")


def build(site_url):
    src = (ROOT / "page.html").read_text(encoding="utf-8")
    split = src.index("</style>") + len("</style>")
    head_part, body_part = src[:split].strip(), src[split:].strip()
    site_url = site_url.rstrip("/")
    head = f"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="{DESCRIPTION}">
<meta name="theme-color" content="#0e0c0b">
<meta property="og:type" content="website">
<meta property="og:title" content="The Underground: Reborn">
<meta property="og:description" content="{DESCRIPTION}">
<meta property="og:url" content="{site_url}/">
<meta property="og:image" content="{site_url}/assets/icon-512.png">
<meta name="twitter:card" content="summary">
<link rel="icon" type="image/png" sizes="32x32" href="assets/favicon-32.png">
<link rel="apple-touch-icon" href="assets/apple-touch-icon.png">
{head_part}"""
    html = f"""<!doctype html>
<html lang="en">
<head>
{head}
<style>body {{ margin: 0; }} img {{ max-width: 100%; }}</style>
</head>
<body>
{body_part}
</body>
</html>
"""
    (ROOT / "index.html").write_bytes(html.encode("utf-8"))
    print("wrote index.html for", site_url)


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else SITE_URL)
