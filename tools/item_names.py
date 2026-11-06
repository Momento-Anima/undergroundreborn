#!/usr/bin/env python3
"""
Build a classname -> player-facing display name catalog for the public price-lookup website.

WHY THIS EXISTS: the Expansion Market files only carry classnames (e.g. "M4A1_Black"); a public
price page needs "M4A1 (Black)". The names live in two places: each class's displayName in the
derapified config (CfgVehicles/CfgWeapons/CfgMagazines/CfgGlasses/CfgNonAIVehicles), which is
either literal text or a "$STR_key" that must be looked up in a stringtable.csv.

It reuses the server repo's tools (read-only, nothing in the server repo, Workshop folders or
test/live is modified): pbo_config.read_index_full (robust against PBO Tools obfuscated headers)
and pbo_catalogue.config_text (CfgConvert derapify). Only the index plus the config.bin /
stringtable.csv entries of each PBO are read, never the whole (multi-GB) archive. Compressed
entries are NOT supported (tools/AGENTS.md); such PBOs/entries are reported as skipped.

Rules: classnames matched case-insensitively; when a class has no displayName it inherits from
its parent chain only if the parent is a real named item (stops at *_Base); later-loaded
definitions override earlier ones (vanilla first, then mods in docs/live-mod-folders.txt order).

Usage:  python tools/item_names.py            (writes G:\\TU\\undergroundreborn\\data_build\\*)
Output is written as UTF-8 WITHOUT a BOM.
"""
import csv
import glob
import io
import json
import os
import re
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

REPO = r"G:\TU\dayz-deer-isle"
sys.path.insert(0, os.path.join(REPO, "tools"))
import pbo_config as pc          # noqa: E402
import pbo_catalogue as cat      # noqa: E402

DAYZ = r"G:\SteamLibrary\steamapps\common\DayZ"
WS = os.path.join(DAYZ, "!Workshop")
WS_CONTENT = r"G:\SteamLibrary\steamapps\workshop\content\221100"
OUT = r"G:\TU\undergroundreborn\data_build"
MARKET = os.path.join(REPO, r"DayZServerData\ExpansionMod\Market")
SECTIONS = {"cfgvehicles", "cfgweapons", "cfgmagazines", "cfgglasses", "cfgnonaivehicles"}
TOK = re.compile(
    r'"[^"\r\n]*"'
    r'|\bdisplayName\s*=\s*"([^"]*)"\s*;'
    r'|\bclass\s+(\w+)\s*(?::\s*(\w+))?\s*([{;])'
    r'|[{}]')


def parse_config_sections(text):
    """Like parse_config but only for classes inside the wanted Cfg* sections."""
    res = []
    depth = 0
    stack = []
    for m in TOK.finditer(text):
        tok = m.group(0)
        if tok.startswith('"'):
            continue
        if tok == "{":
            depth += 1
        elif tok == "}":
            depth -= 1
            while stack and stack[-1][3] > depth:
                n, p, d, dp = stack.pop()
                if dp == 2 and stack and stack[0][0].lower() in SECTIONS:
                    res.append((n, p, d))
        elif m.group(2) is not None:
            if m.group(4) == "{":
                depth += 1
                stack.append([m.group(2), m.group(3) or "", None, depth])
        else:
            if len(stack) >= 2 and stack[-1][3] == 2 and stack[0][0].lower() in SECTIONS:
                stack[-1][2] = m.group(1)
    return res


def load_stringtable(blob):
    txt = blob.decode("utf-8-sig", "replace")
    out = {}
    rd = csv.reader(io.StringIO(txt))
    try:
        hdr = next(rd)
    except StopIteration:
        return out
    low = [h.strip().lower() for h in hdr]
    ie = low.index("english") if "english" in low else None
    io_ = low.index("original") if "original" in low else None
    for row in rd:
        if not row or not row[0].strip():
            continue
        key = row[0].strip().lower()
        v = ""
        if ie is not None and ie < len(row):
            v = row[ie].strip()
        if not v and io_ is not None and io_ < len(row):
            v = row[io_].strip()
        if v:
            out[key] = v.replace("<br>", " ").replace("\\n", " ")
    return out


def process_pbo(path):
    """Return dict: classes [(n,p,d)], strings {}, skipped [reasons], configs int."""
    res = {"classes": [], "strings": {}, "skipped": [], "configs": 0}
    try:
        entries, _ = pc.read_index(path)
    except Exception as e:
        res["skipped"].append("unreadable index: %s" % e)
        return res
    cfg_entries = []
    with open(path, "rb") as fh:
        for e in entries:
            base = os.path.basename(e["name"].replace("\\", "/")).lower()
            if base in ("config.bin", "config.cpp"):
                if e["pack"] != 0 or e["size"] < 120:
                    if e["pack"] != 0:
                        res["skipped"].append("compressed entry %s" % e["name"])
                    continue
                cfg_entries.append(e)
            elif base == "stringtable.csv":
                if e["pack"] != 0:
                    res["skipped"].append("compressed entry %s" % e["name"])
                    continue
                fh.seek(e["offset"])
                res["strings"].update(load_stringtable(fh.read(e["size"])))
    for e in cfg_entries:
        idx = [(e["name"], e["offset"], e["size"], 0)]
        try:
            text = cat.config_text(path, idx)
        except Exception as ex:
            text = None
        if not text:
            res["skipped"].append("config not derapified: %s" % e["name"])
            continue
        res["configs"] += 1
        res["classes"].extend(parse_config_sections(text))
    return res


def resolve_folders():
    names = [l.strip() for l in open(os.path.join(REPO, r"docs\live-mod-folders.txt"), encoding="utf-8") if l.strip()]
    found, missing = [], []
    for n in names:
        cands = [os.path.join(WS, n + "@"), os.path.join(WS, n)]
        stem = n.lstrip("@")
        if stem.startswith("TUR_"):
            cands.append(os.path.join(r"G:\TUR", stem, n))
        d = next((c for c in cands if os.path.isdir(os.path.join(c, "addons"))), None)
        (found if d else missing).append((n, d) if d else n)
    return found, missing


def market_classes():
    per_file = {}
    for f in sorted(glob.glob(os.path.join(MARKET, "*.json"))):
        try:
            d = json.load(open(f, encoding="utf-8-sig"))
        except Exception as e:
            print("market unreadable", f, e)
            continue
        s = set()
        for it in d.get("Items", []):
            cn = it.get("ClassName")
            if cn:
                s.add(cn.lower())
            for v in it.get("Variants") or []:
                if isinstance(v, str):
                    s.add(v.lower())
        per_file[os.path.basename(f)] = s
    return per_file


def main():
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    found, missing = resolve_folders()
    jobs = []   # (label, pbo path) in load order: vanilla, DeerIsle dta, then mods
    for p in sorted(glob.glob(os.path.join(DAYZ, "dta", "*.pbo"))):
        jobs.append(("vanilla dta", p))
    for p in sorted(glob.glob(os.path.join(DAYZ, "Addons", "*.pbo"))):
        jobs.append(("vanilla Addons", p))
    for n, d in found:
        for p in sorted(glob.glob(os.path.join(d, "addons", "*.pbo"))):
            jobs.append((n, p))
    print("%d pbos from %d folders (%d unresolved)" % (len(jobs), len(found), len(missing)), flush=True)

    with ThreadPoolExecutor(8) as ex:
        results = list(ex.map(lambda j: process_pbo(j[1]), jobs))

    classes = {}      # lower -> {"disp": raw or "", "parent": str}
    strings = {}
    skipped = []
    for (label, p), r in zip(jobs, results):
        for s in r["skipped"]:
            skipped.append((label, os.path.basename(p), s))
        strings.update(r["strings"])
        for n, par, d in r["classes"]:
            c = classes.setdefault(n.lower(), {"disp": "", "parent": ""})
            if par:
                c["parent"] = par.lower()
            if d:
                c["disp"] = d

    def lookup(raw):
        if not raw:
            return ""
        if raw.startswith("$"):
            raw = raw[1:]
        if raw.upper().startswith("STR_"):
            return strings.get(raw.lower(), "")
        return raw.strip()

    memo = {}
    base_derived = set()

    def name_of(cn, depth=0):
        cn = cn.lower()
        if cn in memo:
            return memo[cn]
        memo[cn] = ""
        c = classes.get(cn)
        if not c or depth > 40:
            return ""
        v = lookup(c["disp"])
        if not v and c["parent"] and not c["parent"].endswith("_base") and c["parent"] != cn:
            v = name_of(c["parent"], depth + 1)
        elif not v and c["parent"].endswith("_base") and c["parent"] in classes:
            # Deviation from "never inherit from *_Base", deliberately narrow: some mods put the real
            # item name on a family Base (AD_RMR_Base -> "$STR_AD_RMR0", AA12_Base -> "AA12"). Take it
            # only when that Base carries its own displayName directly; never climb further.
            v = lookup(classes[c["parent"]]["disp"])
            if v:
                base_derived.add(cn)
        if cn.endswith("_base"):
            v = lookup(c["disp"])
        memo[cn] = v
        return v

    per_file = market_classes()
    allm = set().union(*per_file.values())
    names = {}
    for cn in classes:
        v = name_of(cn)
        if v and not v.startswith("$"):
            names[cn] = v
    # sanity: placeholder names
    for cn in list(names):
        if names[cn].strip().lower() in ("", "unknown", "todo", "none"):
            del names[cn]

    out = {k: names[k] for k in sorted(names)}
    with open(os.path.join(OUT, "item_names.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=0, sort_keys=True)

    resolved = {c for c in allm if c in names}
    unres = sorted(allm - resolved)
    cats_of = defaultdict(int)
    for s in per_file.values():
        for c in s:
            if c not in names:
                cats_of[c] += 1
    top = sorted(unres, key=lambda c: (-cats_of[c], c))[:60]
    not_in_cfg = [c for c in unres if c not in classes]
    L = []
    L.append("# item_names coverage report\n")
    L.append("Generated by tools/item_names.py in %.0fs. %d classes parsed from %d PBOs, %d stringtable keys.\n"
             % (time.time() - t0, len(classes), len(jobs), len(strings)))
    L.append("Catalog entries (item_names.json): %d\n" % len(names))
    L.append("## Overall\n")
    L.append("Market classnames (Items + Variants, distinct, lowercase): %d; resolved: %d (%.1f%%); unresolved: %d "
             "(of which %d have no class definition in any readable PBO)\n"
             % (len(allm), len(resolved), 100.0 * len(resolved) / max(1, len(allm)), len(unres), len(not_in_cfg)))
    L.append("## Per market category file\n")
    L.append("| file | resolved | total | % |\n|---|---|---|---|")
    for f, s in sorted(per_file.items()):
        r = sum(1 for c in s if c in names)
        L.append("| %s | %d | %d | %.1f |" % (f, r, len(s), 100.0 * r / max(1, len(s))))
    L.append("\n## Mod folders not resolved to an addons dir\n")
    L.extend(["- %s" % m for m in missing] or ["- none"])
    L.append("\n## Skipped PBOs / entries\n")
    L.extend(["- %s / %s: %s" % s for s in skipped] or ["- none"])
    L.append("\n## 60 most important unresolved classnames (by number of market categories carrying them)\n")
    L.append("| classname | categories | has class def |\n|---|---|---|")
    for c in top:
        L.append("| %s | %d | %s |" % (c, cats_of[c], "yes" if c in classes else "no"))
    with open(os.path.join(OUT, "item_names_report.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(L) + "\n")
    with open(os.path.join(OUT, "item_names_from_base_parent.txt"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join("%s\t%s" % (c, names[c]) for c in sorted(base_derived) if c in names) + "\n")
    with open(os.path.join(OUT, "item_names_unresolved.txt"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(unres) + "\n")
    print("resolved %d/%d (%.1f%%), %.0fs" % (len(resolved), len(allm), 100.0 * len(resolved) / max(1, len(allm)), time.time() - t0))


if __name__ == "__main__":
    main()
