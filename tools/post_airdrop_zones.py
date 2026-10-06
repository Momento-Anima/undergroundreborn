"""Push the possible airdrop zones (name, x, z, radius ONLY) to the website's private admin store.

WHY: the admin live map shows where an airdrop could land. The zones are static in HM_Settings_AirDropPlus.json, so this
runs once (and again if the zones change). Read-only on that file, no game-server contact, no loot or type data is sent.

  python tools/post_airdrop_zones.py              dry run: prints how many zones and the first rows, posts nothing
  python tools/post_airdrop_zones.py --post       POST to https://api.theundergroundserver.com/ingest/airdrops

Needs %USERPROFILE%\\.tur-bridge\\events_ingest.json {"secret": "<INGEST_SECRET>"} (outside the repo; never printed).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

SRC = r"G:\TU\dayz-deer-isle\DayZServerData\Hunter_Mods\HM_Airdrop_Plus\HM_Settings_AirDropPlus.json"
API = "https://api.theundergroundserver.com/ingest/airdrops"
SECRET_FILE = os.path.join(os.environ["USERPROFILE"], ".tur-bridge", "events_ingest.json")


def zones():
    d = json.load(open(SRC, encoding="utf-8-sig"))
    out = []
    for z in d["airDropZones"]:
        p = z["position"]
        out.append({"locationName": z["locationName"], "x": round(p[0], 1), "z": round(p[2], 1), "radius": z["radius"]})
    return out


def main():
    zs = zones()
    print("zones:", len(zs))
    for z in zs[:3]:
        print("  ", z)
    if "--post" not in sys.argv:
        print("dry run: nothing posted")
        return 0
    secret = json.load(open(SECRET_FILE, encoding="utf-8"))["secret"]
    # curl, not urllib: this PC's Python has an out-of-date certificate store ("certificate has expired"); curl uses Windows'.
    # The secret goes in a temp header file (curl -H @file), never on the command line.
    tmp = tempfile.mkdtemp()
    try:
        body, hdr = os.path.join(tmp, "b.json"), os.path.join(tmp, "h.txt")
        open(body, "w", encoding="utf-8").write(json.dumps({"schema": 1, "zones": zs}))
        NL = chr(10)
        open(hdr, "w", encoding="ascii").write("X-Ingest-Secret: " + secret + NL + "Content-Type: application/json" + NL)
        r = subprocess.run(["curl", "-s", "-w", NL + "status %{http_code}", "-X", "POST", "-H", "@" + hdr, "--data-binary", "@" + body, API],
                           capture_output=True, text=True, encoding="utf-8")
        print(r.stdout[-300:], r.stderr[-200:])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
