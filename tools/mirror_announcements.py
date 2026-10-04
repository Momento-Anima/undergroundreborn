#!/usr/bin/env python3
"""Mirror our Discord announcements onto the website's News page.

WHY THIS EXISTS: Momento, 2026-10-03: the News page should only mirror what we put out as Discord announcements. He follows
the public "The Underground" announcements channel into the private #announcement-mirror channel of the staff server
(Discord's "Follow" feature), and this script turns what arrives there into data/news.json (+ images in assets/news/).
build.py renders the News page from that file.

WHAT REACHES THE SITE (and nothing else):
  - only messages in #announcement-mirror that are crossposts delivered by the channel-follower webhook
    (message.flags has IS_CROSSPOST, and the webhook is a type-2 "Channel Follower" webhook);
  - text, embed title/description/fields, and IMAGE attachments (re-saved without metadata, resized, stored locally:
    Discord CDN links expire);
  - mentions, custom emoji, @everyone/@here, spoilers and timestamps are cleaned or removed.
No other channel is ever read.

SECRETS: the bot token comes from this PC's DISCORD_BOT_TOKEN user environment variable (as tools/discord_log_layout.py in the
server repo does). It is never written to a repo, to the Cloudflare Worker, or to the site. Output is public announcement text only.

    python tools/mirror_announcements.py            # fetch, write data/news.json + assets/news/ if anything changed
    python tools/mirror_announcements.py --check    # health only: follower link present? newest post age? (warns on stale)
    python tools/mirror_announcements.py --selftest # offline tests of the filter and the cleaning rules (no network)

Exit codes: 0 ok (changed or not), 2 = the data file changed (the scheduled task uses this to commit), 1 = error.
"""
import argparse
import datetime
import io
import json
import os
import re
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GUILD = "676213522463457325"                 # Radical Dreamers (staff server): destination of the Follow link
CHANNEL_NAME = "announcements-mirror"      # created by Momento; the public announcements are followed into it
# Only follower webhooks whose NAME contains one of these (after Unicode normalisation, lowercase) are mirrored. The public
# server follows two source channels ("Announcements" and "Announcements-DayZ"); Momento chose to mirror BOTH (2026-10-04), and
# both names contain "announcements". Anything else that is ever followed into the channel stays out unless added here.
SOURCES = ("announcements",)
API = "https://discord.com/api/v10"
DATA = os.path.join(ROOT, "data", "news.json")
IMG_DIR = os.path.join(ROOT, "assets", "news")
STATE = os.path.join(os.path.expanduser("~"), ".tur-bridge", "news_mirror_state.json")
STALE_DAYS = 45
IS_CROSSPOST = 1 << 1
MAX_IMG_BYTES = 8 * 1024 * 1024
MAX_IMG_W = 1600


# ----------------------------------------------------------------------------- cleaning (pure functions, tested offline)
def clean(text):
    """Strip things that must not be republished or that mean nothing on a web page."""
    if not text:
        return ""
    text = re.sub(r"<a?:\w+:\d+>", "", text)                       # custom emoji
    text = re.sub(r"<@[!&]?\d+>|<#\d+>|<id:\w+>", "", text)         # user/role/channel mentions, guild navigation
    text = re.sub(r"@(everyone|here)\b", r"\1", text)               # never leave a ping-looking token
    text = re.sub(r"\|\|.*?\|\|", "", text, flags=re.S)             # spoilers
    def stamp(m):
        return datetime.datetime.fromtimestamp(int(m.group(1)), datetime.timezone.utc).strftime("%Y-%m-%d")
    text = re.sub(r"<t:(\d+)(?::[a-zA-Z])?>", stamp, text)         # Discord timestamps
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_title(text):
    """First line becomes the title when the post has no embed title."""
    lines = text.split("\n")
    first = ""
    for i, ln in enumerate(lines):
        if ln.strip():
            first, rest = ln.strip(), "\n".join(lines[i + 1:]).strip()
            break
    else:
        return "", ""
    t = re.sub(r"^#{1,3}\s*", "", first)
    t = re.sub(r"[*_~`]+", "", t).strip()
    if len(t) > 90:
        return "", text                                             # a long first line is body text, not a title
    return t, rest


def sectionize(body):
    """Announcements are often several emoji-headed sections of bullets. Turn each header line (short, no full stop, followed
    by a bullet) into a '### ' heading. Returns (text, number_of_headers)."""
    lines = body.split("\n")
    bullet = re.compile(r"^[\u2022\-*]\s")
    out, n = [], 0
    for i, ln in enumerate(lines):
        st = ln.strip()
        nxt = next((x.strip() for x in lines[i + 1:] if x.strip()), "")
        plain = re.sub(r"[*_~`]+", "", st).strip()
        if st and not bullet.match(st) and len(plain) <= 70 and not plain.endswith((".", ":", "!", "?")) and bullet.match(nxt):
            out.append("### " + plain)
            n += 1
        else:
            out.append(ln)
    return "\n".join(out), n


def wanted(msg, follower_ids):
    """The ONLY messages that may reach the site."""
    if msg.get("type") not in (0, 19):
        return False
    if not (msg.get("flags", 0) & IS_CROSSPOST):
        return False
    if follower_ids and msg.get("webhook_id") not in follower_ids:
        return False
    return True


def to_item(msg):
    """Message dict -> news item WITHOUT images (images are fetched separately)."""
    content = clean(msg.get("content", ""))
    title, body, fields = "", content, []
    embs = msg.get("embeds") or []
    if embs:
        e = embs[0]
        title = clean(e.get("title", ""))
        desc = clean(e.get("description", ""))
        body = (content + "\n\n" + desc).strip() if desc else content
        fields = [{"name": clean(f.get("name", "")), "value": clean(f.get("value", ""))} for f in e.get("fields", [])
                  if f.get("name") or f.get("value")]
    if not title:
        sectioned, n = sectionize(body)
        if n >= 2:
            title, body = "Server update", sectioned
        elif n == 1 and sectioned.lstrip().startswith("### "):
            first, _, rest = sectioned.lstrip().partition("\n")
            title, body = first[4:].strip(), rest.strip()
        else:
            title, body = split_title(body)
    return {
        "id": msg["id"],
        "date": msg["timestamp"][:10],
        "title": title or "Announcement",
        "text": body,
        "fields": fields,
        "images": [],
    }


def image_urls(msg):
    urls = []
    for a in msg.get("attachments") or []:
        ct = (a.get("content_type") or "").lower()
        if ct.startswith("image/") and a.get("size", 0) <= MAX_IMG_BYTES:
            urls.append((a["url"], a.get("description") or ""))
    for e in msg.get("embeds") or []:
        u = (e.get("image") or {}).get("url") or ""
        if u.startswith(("https://cdn.discordapp.com/", "https://media.discordapp.net/")):
            urls.append((u, ""))
    return urls


# ----------------------------------------------------------------------------- network
def token():
    t = os.environ.get("DISCORD_BOT_TOKEN")
    if t:
        return t
    import winreg
    return winreg.QueryValueEx(winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment"), "DISCORD_BOT_TOKEN")[0]


def call(path, tok, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method, headers={
        "Authorization": "Bot " + tok, "User-Agent": "TUR-Phoenix (news mirror, 1)", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        return json.loads(raw) if raw else {}


def channel_id(tok):
    for c in call("/guilds/%s/channels" % GUILD, tok):
        if c["type"] == 0 and c["name"] == CHANNEL_NAME:
            return c["id"]
    raise SystemExit("#%s not found in the staff server" % CHANNEL_NAME)


def norm(name):
    """Source channel names use fancy Unicode letters; NFKC turns them back into plain ones."""
    import unicodedata
    return unicodedata.normalize("NFKC", name or "").lower()


def all_followers(tok, cid):
    return [h for h in call("/channels/%s/webhooks" % cid, tok) if h.get("type") == 2]


def follower_webhooks(tok, cid):
    """Ids of the follower webhooks whose source we mirror."""
    return {h["id"] for h in all_followers(tok, cid) if any(src in norm(h.get("name", "")) for src in SOURCES)}


def fetch_messages(tok, cid, limit=200):
    out, before = [], None
    while len(out) < limit:
        q = "/channels/%s/messages?limit=100" % cid + ("&before=%s" % before if before else "")
        page = call(q, tok)
        if not page:
            break
        out += page
        before = page[-1]["id"]
        if len(page) < 100:
            break
    return out


def save_image(url, msg_id, n):
    from PIL import Image
    req = urllib.request.Request(url, headers={"User-Agent": "TUR-Phoenix (news mirror, 1)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read(MAX_IMG_BYTES + 1)
    if len(raw) > MAX_IMG_BYTES:
        return None
    im = Image.open(io.BytesIO(raw))
    fmt = (im.format or "").upper()
    if fmt not in ("PNG", "JPEG", "GIF", "WEBP"):
        return None
    os.makedirs(IMG_DIR, exist_ok=True)
    ext = {"PNG": "png", "JPEG": "jpg", "GIF": "gif", "WEBP": "webp"}[fmt]
    name = "%s-%d.%s" % (msg_id, n, ext)
    path = os.path.join(IMG_DIR, name)
    if fmt == "GIF":                                               # animated: keep the bytes, no metadata of concern
        open(path, "wb").write(raw)
    else:
        if im.width > MAX_IMG_W:
            im = im.resize((MAX_IMG_W, round(im.height * MAX_IMG_W / im.width)))
        im.save(path, fmt, **({"quality": 88} if fmt in ("JPEG", "WEBP") else {}))     # re-save: drops EXIF/metadata
    return "/assets/news/" + name


# ----------------------------------------------------------------------------- state / health
def load_state():
    try:
        return json.load(open(STATE, encoding="utf-8"))
    except Exception:
        return {}


def save_state(s):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    open(STATE, "w", encoding="utf-8").write(json.dumps(s))


def health(tok, cid, items, warn):
    """Problems are always printed; a Discord warning is only posted once a Follow link has existed (state.seen_follow),
    so nobody is nagged before the link is set up."""
    st = load_state()
    allf = all_followers(tok, cid)
    has_follow = bool(follower_webhooks(tok, cid))
    for h in allf:
        mirrored = any(src in norm(h.get("name", "")) for src in SOURCES)
        print("follow source: %s -> %s" % (norm(h.get("name", "")), "MIRRORED" if mirrored else "ignored"))
    if has_follow and not st.get("seen_follow"):
        st["seen_follow"] = True
        save_state(st)
    problems = []
    if not has_follow:
        problems.append("no follower webhook for the DayZ announcements in #%s: the Follow link is missing or was removed" % CHANNEL_NAME)
    newest = max((i["date"] for i in items), default=None)
    if newest:
        age = (datetime.date.today() - datetime.date.fromisoformat(newest)).days
        if age > STALE_DAYS:
            problems.append("newest mirrored announcement is %d days old (limit %d): check the Follow link, or nobody Published" % (age, STALE_DAYS))
    elif has_follow:
        problems.append("the Follow link exists but nothing has been Published and mirrored yet")
    for p in problems:
        print("WARNING:", p)
    if warn and problems and st.get("seen_follow"):
        today = datetime.date.today().isoformat()
        if st.get("last_warn") != today:                           # at most one Discord warning per day
            call("/channels/%s/messages" % cid, tok, "POST", {
                "content": "Website news mirror: " + "; ".join(problems), "allowed_mentions": {"parse": []}})
            st["last_warn"] = today
            save_state(st)
    if not problems:
        print("health: ok (follower link present, newest announcement %s)" % newest)
    return problems


# ----------------------------------------------------------------------------- main
def selftest():
    ok = True

    def check(name, cond):
        nonlocal ok
        print(("PASS " if cond else "FAIL ") + name)
        ok = ok and cond
    c = clean("Hi <@123> and <@&456> in <#789> <:x:111> @everyone ||secret|| at <t:1790000000:F>")
    check("mentions, emoji, spoilers, everyone removed", "<@" not in c and "<#" not in c and "<:" not in c and "secret" not in c and "@everyone" not in c and "everyone" in c)
    check("timestamp becomes a date", re.search(r"\d{4}-\d{2}-\d{2}", c) is not None)
    t, b = split_title("# Big news\nWe now have **a thing**.")
    check("first line becomes the title", t == "Big news" and b.startswith("We now have"))
    check("a long first line is not a title", split_title("x" * 120)[0] == "")
    follower = {"W1"}
    good = {"id": "10", "type": 0, "flags": 2, "webhook_id": "W1", "timestamp": "2026-10-04T10:00:00+00:00", "content": "# Hello\nBody", "embeds": [], "attachments": []}
    check("a followed crosspost is wanted", wanted(good, follower))
    check("a plain webhook post is NOT wanted", not wanted(dict(good, flags=0), follower))
    check("a crosspost from another webhook is NOT wanted", not wanted(dict(good, webhook_id="W9"), follower))
    check("a human message is NOT wanted", not wanted(dict(good, flags=0, webhook_id=None), follower))
    check("system messages are NOT wanted", not wanted(dict(good, type=7), follower))
    it = to_item(dict(good, embeds=[{"title": "Embed title", "description": "Embed body", "fields": [{"name": "A", "value": "B"}]}]))
    check("embed title/description/fields are used", it["title"] == "Embed title" and "Embed body" in it["text"] and it["fields"] == [{"name": "A", "value": "B"}])
    check("item has a date and no images yet", it["date"] == "2026-10-04" and it["images"] == [])
    bold = "".join(chr(0x1D5D4 + ord(c) - 65) if "A" <= c <= "Z" else chr(0x1D5EE + ord(c) - 97) if "a" <= c <= "z" else c for c in "Announcements-DayZ")
    check("fancy Unicode source names normalise", "announcements-dayz" in norm("The Underground #📢│" + bold) and bold != "Announcements-DayZ")
    def fancy(txt):
        return "".join(chr(0x1D5D4 + ord(c) - 65) if "A" <= c <= "Z" else chr(0x1D5EE + ord(c) - 97) if "a" <= c <= "z" else c for c in txt)
    names = ["The Underground #📢│" + fancy("Announcements"), "The Underground #📢│" + fancy("Announcements-DayZ")]
    check("both source channels are mirrored", all(any(x in norm(n) for x in SOURCES) for n in names))
    check("an unrelated followed channel is NOT mirrored", not any(x in norm("Some Game #patch-notes") for x in SOURCES))
    multi = "\U0001F3C5 **Notoriety & Factions**\n\u2022 one\n\u2022 two\n\n\U0001F996 **Wildlife**\n\u2022 three"
    it2 = to_item(dict(good, content=multi))
    check("a multi-section post gets a generic title and ### headings", it2["title"] == "Server update" and it2["text"].count("### ") == 2)
    one = to_item(dict(good, content="Update time\n\u2022 a\n\u2022 b"))
    check("a single header becomes the title", one["title"] == "Update time" and one["text"].startswith("\u2022 a"))
    print("SELFTEST", "OK" if ok else "FAILED")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--warn", action="store_true", help="with --check or a normal run: post a once-a-day warning to #announcement-mirror")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    tok = token()
    cid = channel_id(tok)
    old = json.load(open(DATA, encoding="utf-8")) if os.path.exists(DATA) else {"items": []}
    items = {i["id"]: i for i in old["items"]}
    if a.check:
        health(tok, cid, list(items.values()), a.warn)
        return 0
    followers = follower_webhooks(tok, cid)
    changed = False
    for msg in fetch_messages(tok, cid):
        if not wanted(msg, followers):
            continue
        if msg["id"] in items and items[msg["id"]].get("done"):
            continue
        item = to_item(msg)
        for n, (url, alt) in enumerate(image_urls(msg), 1):
            try:
                src = save_image(url, msg["id"], n)
            except Exception as e:                                  # one bad image must not block the post
                print("image skipped:", e)
                src = None
            if src:
                item["images"].append({"src": src, "alt": clean(alt) or "Image from the announcement"})
        item["done"] = True
        twin = next((i for i in items.values() if i["id"] != item["id"] and i["title"] == item["title"] and i["text"] == item["text"]), None)
        if twin:                                                    # same post sent to both channels: keep one
            print("duplicate skipped:", item["date"], item["title"])
            continue
        if items.get(msg["id"]) != item:
            items[msg["id"]] = item
            changed = True
            print("mirrored:", item["date"], item["title"])
    out = {"updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
           "items": sorted(items.values(), key=lambda i: (i["date"], i["id"]), reverse=True)}
    health(tok, cid, out["items"], a.warn)
    if changed:
        os.makedirs(os.path.dirname(DATA), exist_ok=True)
        open(DATA, "wb").write((json.dumps(out, indent=1, ensure_ascii=False) + "\n").encode("utf-8"))
        return 2
    print("nothing new")
    return 0


if __name__ == "__main__":
    sys.exit(main())
