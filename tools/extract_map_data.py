"""Build assets/map-data.json from the server repo: zones, trader hubs, dinosaur areas.

Reads (never writes) the server repo:
  DayZServerData/NinjinsPvPPvE/Config/zones/<PVP|PVE|SAFEZONE|VISUAL>/*.json
  mpmissions/Empty.deerisle/expansion/traders/*.map   (trader NPC positions)
  mpmissions/Empty.deerisle/env/*_territories.xml     (dinosaur territories)

Zone type codes are Ninjins': 1 = PvP, 2 = PvE, 3 = label only, 5 = safe zone.
Deer Isle is 16384 m square (world.pbo centerPosition 8192, 8192).

    python tools/extract_map_data.py [G:\\TU\\dayz-deer-isle]
"""
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
REPO = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"G:\TU\dayz-deer-isle")
OUT = SITE / "assets" / "map-data.json"

WORLD = 16384
TYPES = {1: "pvp", 2: "pve", 3: "label", 5: "safe"}

# Trader .map files -> what the pin says. The file name is the hub.
HUBS = {
    "GrootsHill_Traders": "Groot's Hill",
    "Waldoboro_Trader_Vending": "Waldoboro",
    "ShipHoleHarbor_Trader": "Ship Hole Harbor",
    "BlackMarket_Trader_Vending": "Black Market",
    "GreyMarket_Trader_Vending": "Grey Market",
    "Collectibles_Traders": "Collectibles",
    "SonsofDeerIsle_Traders": "Sons of Deer Isle",
    "TheHuntsman_Traders": "The Huntsman",
}

DINOS = {  # territory file -> label
    "trex_territories.xml": "T-Rex",
    "raptorstandard_territories.xml": "Raptors",
    "raptormid_territories.xml": "Raptors",
    "raptortough_territories.xml": "Raptors",
}


def clean(name):
    name = re.sub(r"^\((GAS|Safe|PvE|PvP|Quest|Mining)\)\s*", "", name)
    name = re.sub(r"\s+(1[0-2]|[1-9])$", "", name)  # "Paris Island 3" -> "Paris Island"
    return name.replace("AREA 42", "Area 42").strip()


def zones():
    out = []
    root = REPO / "DayZServerData" / "NinjinsPvPPvE" / "Config" / "zones"
    for f in sorted(root.rglob("*.json")):
        z = json.loads(f.read_text(encoding="utf-8-sig"))
        t = TYPES.get(z.get("type"))
        if not t or z.get("Hide") or z.get("radius", 0) <= 0:
            continue
        raw = z["name"]
        gas = raw.startswith("(GAS)")
        if t == "label" and not gas:
            continue                                  # shop labels, not zones
        out.append({
            "name": clean(raw), "type": "gas" if gas else t,
            "x": round(z["center"][0]), "z": round(z["center"][2]),
            "r": round(z["radius"]),
        })
    # A GAS circle and a PvP circle at the same centre are one place: keep the PvP
    # circle and flag it.
    gas = [g for g in out if g["type"] == "gas"]
    keep = []
    for z in out:
        if z["type"] == "gas":
            twin = next((p for p in out if p["type"] == "pvp" and abs(p["x"] - z["x"]) < 20
                         and abs(p["z"] - z["z"]) < 20), None)
            if twin:
                twin["gas"] = True
                continue
        keep.append(z)
    return keep


def traders():
    out = []
    root = REPO / "mpmissions" / "Empty.deerisle" / "expansion" / "traders"
    for stem, label in HUBS.items():
        f = root / f"{stem}.map"
        if not f.exists():
            print("!! missing", f)
            continue
        pts = []
        for line in f.read_text(encoding="utf-8-sig").splitlines():
            parts = line.split("|")
            if len(parts) < 2:
                continue
            x, _, z = (float(v) for v in parts[1].split())
            pts.append((x, z))
        out.append({"name": label, "x": round(sum(p[0] for p in pts) / len(pts)),
                    "z": round(sum(p[1] for p in pts) / len(pts)), "npcs": len(pts)})
    return out


def dinos():
    out = defaultdict(list)
    env = REPO / "mpmissions" / "Empty.deerisle" / "env"
    for fname, label in DINOS.items():
        f = env / fname
        if not f.exists():
            print("!! missing", f)
            continue
        for zone in ET.parse(f).getroot().iter("zone"):
            out[label].append({"x": round(float(zone.get("x"))), "z": round(float(zone.get("z"))),
                               "r": max(round(float(zone.get("r"))), 60)})
    return [{"name": k, "areas": v} for k, v in out.items()]


def main():
    data = {"world": WORLD, "zones": zones(), "traders": traders(), "dinos": dinos()}
    OUT.write_bytes((json.dumps(data, indent=1) + "\n").encode("utf-8"))
    print(f"{OUT}: {len(data['zones'])} zones, {len(data['traders'])} trader hubs, "
          f"{sum(len(d['areas']) for d in data['dinos'])} dino areas")


if __name__ == "__main__":
    main()
