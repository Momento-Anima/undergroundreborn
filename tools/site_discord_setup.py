#!/usr/bin/env python3
"""Create the private staff channel that the website's appeals form posts into, plus its webhook.

WHY THIS EXISTS: the appeals form (worker/worker.js, /appeal) delivers into a Discord channel through a webhook.
That channel must be visible to staff only, and the webhook URL is a secret: it goes into the Worker's
APPEALS_WEBHOOK secret (pasted by hand in the Cloudflare dashboard), never into chat or this repo.

Idempotent: finds the category and channel by name, and reuses the webhook named "Website appeals".
The bot token comes from the DISCORD_BOT_TOKEN user environment variable (same as tools/discord_log_layout.py in
the server repo). The webhook URL is written to %USERPROFILE%/.tur-bridge/site_appeals_webhook.txt and is never
printed.

    python tools/site_discord_setup.py plan
    python tools/site_discord_setup.py apply
    python tools/site_discord_setup.py mirror        # #announcement-mirror: where the Discord Follow link delivers (no webhook needed)

Test setup (2026-10-03): the bot only sits in "Radical Dreamers", so that is where this runs. When the public
"The Underground" server is opened to the bot, change GUILD and STAFF_ROLES below and run it there.
"""
import json
import os
import sys
import urllib.error
import urllib.request

GUILD = "676213522463457325"                       # Radical Dreamers (test)
STAFF_ROLES = {"scion": "676214961999183872", "council": "676214644385251408"}
BOT_ROLE = "1549499652494336063"                   # Phoenix
CATEGORY = "Website"
CHANNEL = "site-appeals"
HOOK = "Website appeals"
MIRROR = "announcement-mirror"   # destination of the Discord Follow link (news mirror)
OUT = os.path.join(os.path.expanduser("~"), ".tur-bridge", "site_appeals_webhook.txt")
API = "https://discord.com/api/v10"
VIEW, SEND, HISTORY, MANAGE_HOOKS = 1 << 10, 1 << 11, 1 << 16, 1 << 29


def token():
    t = os.environ.get("DISCORD_BOT_TOKEN")
    if t:
        return t
    import winreg
    return winreg.QueryValueEx(winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment"), "DISCORD_BOT_TOKEN")[0]


TOKEN = None


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method, headers={
        "Authorization": "Bot " + TOKEN, "User-Agent": "TUR-Phoenix (website setup, 1)", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raise SystemExit("Discord %s %s -> %s %s" % (method, path, e.code, e.read().decode()[:200]))


def overwrites():
    ow = [{"id": GUILD, "type": 0, "allow": "0", "deny": str(VIEW)}]
    for rid in STAFF_ROLES.values():
        ow.append({"id": rid, "type": 0, "allow": str(VIEW | SEND | HISTORY), "deny": "0"})
    ow.append({"id": BOT_ROLE, "type": 0, "allow": str(VIEW | SEND | HISTORY | MANAGE_HOOKS), "deny": "0"})
    return ow


def main():
    global TOKEN
    mode = sys.argv[1] if len(sys.argv) > 1 else "plan"
    TOKEN = token()
    if mode in ("mirror", "mirror-plan"):
        chans = call("GET", "/guilds/%s/channels" % GUILD)
        cat = next((c for c in chans if c["type"] == 4 and c["name"].lower() == CATEGORY.lower()), None)
        ch = next((c for c in chans if c["type"] == 0 and c["name"] == MIRROR), None)
        print("category:", "exists" if cat else "MISSING (run apply first)", "| #%s:" % MIRROR, "exists" if ch else "will create")
        if mode == "mirror" and cat and not ch:
            ch = call("POST", "/guilds/%s/channels" % GUILD, {
                "name": MIRROR, "type": 0, "parent_id": cat["id"], "permission_overwrites": overwrites(),
                "topic": "Destination of the Discord Follow link from the public announcements channel. The website mirrors ONLY the followed posts. Admins only."})
            print("created #%s" % MIRROR)
        return
    chans = call("GET", "/guilds/%s/channels" % GUILD)
    cat = next((c for c in chans if c["type"] == 4 and c["name"].lower() == CATEGORY.lower()), None)
    ch = next((c for c in chans if c["type"] == 0 and c["name"] == CHANNEL), None)
    print("category:", "exists" if cat else "will create", "| channel:", "exists" if ch else "will create")
    if mode != "apply":
        print("(plan only; run `apply`)")
        return
    if not cat:
        cat = call("POST", "/guilds/%s/channels" % GUILD, {"name": CATEGORY, "type": 4, "permission_overwrites": overwrites()})
    if not ch:
        ch = call("POST", "/guilds/%s/channels" % GUILD, {
            "name": CHANNEL, "type": 0, "parent_id": cat["id"], "permission_overwrites": overwrites(),
            "topic": "Messages from the website's Contact admins form. Admins only."})
    hooks = [h for h in call("GET", "/channels/%s/webhooks" % ch["id"]) if h.get("name") == HOOK and h.get("token")]
    h = hooks[0] if hooks else call("POST", "/channels/%s/webhooks" % ch["id"], {"name": HOOK})
    url = "https://discord.com/api/webhooks/%s/%s" % (h["id"], h["token"])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="ascii", newline="") as f:
        f.write(url)
    print("channel #%s ready; webhook %s; URL saved to %s (not printed)" % (CHANNEL, "reused" if hooks else "created", OUT))


if __name__ == "__main__":
    main()
