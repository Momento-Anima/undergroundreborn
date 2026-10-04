"""Builds the Locations page art: assets/loc/*.webp (six hub images) and assets/fol/*.webp (ivy corners + moss).

Source art is NOT in this repo. It lives on Momento's PC (read-only, never modified):
  G:\\TUR\\_art\\locations\\<date>-<hub>-v<N>\\<file>.png        the six hub images
  G:\\TUR\\_art\\foliage\\2026-10-04-white-background-v1\\*.png   foliage drawn on plain white

Run: python tools/make_location_images.py     (needs Pillow and numpy)
Groot's Hill uses its v2 (exterior) image; the others use v1.
"""
import os
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = r"G:\TUR\_art"

HUBS = {   # slug -> source png under G:\TUR\_art\locations
    "groots-hill": r"2026-10-04-groots-hill-market-v2\groots_hill_market_exterior_v2.png",
    "waldoboro": r"2026-10-04-waldoboro-trading-post-v1\waldoboro_trading_post_aerial_v1.png",
    "ship-hole-harbor": r"2026-10-04-ship-hole-harbor-v1\ship_hole_harbor_aerial_v1.png",
    "sons-of-deer-isle": r"2026-10-04-sons-of-deer-isle-v1\sons_of_deer_isle_aerial_v1.png",
    "grey-market": r"2026-10-04-grey-market-v1\grey_market_aerial_v1.png",
    "collectibles-trader": r"2026-10-04-collectibles-trader-v1\collectibles_trader_aerial_v1.png",
}
FOLIAGE = {   # output name -> (source png under G:\TUR\_art\foliage\2026-10-04-white-background-v1, max width)
    "ivy-a": ("01_corner_ivy_v1.png", 900),
    "ivy-b": ("01_corner_ivy_v3.png", 900),
    "moss": ("04_moss_leaf_litter_v1.png", 1800),
}
T0, T1 = 14.0, 70.0   # distance from white: below T0 fully clear, above T1 fully solid


def hubs():
    out = os.path.join(ROOT, "assets", "loc")
    os.makedirs(out, exist_ok=True)
    for slug, rel in HUBS.items():
        im = Image.open(os.path.join(ART, "locations", rel)).convert("RGB")
        im = im.resize((1200, round(im.height * 1200 / im.width)), Image.LANCZOS)
        dst = os.path.join(out, slug + ".webp")
        im.save(dst, "WEBP", quality=80, method=6)
        print("%-20s %dx%d %d KB" % (slug, im.width, im.height, os.path.getsize(dst) // 1024))


def cut_white(path):
    """Remove the white backdrop: soft alpha from the distance to white, then un-mix the white halo."""
    rgb = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    a = np.clip((255.0 - rgb.min(axis=2) - T0) / (T1 - T0), 0, 1)
    af = np.maximum(a, 1e-3)[..., None]
    col = np.clip((rgb - 255.0 * (1 - af)) / af, 0, 255)
    col = np.where(a[..., None] > 0.999, rgb, col)
    a = np.where(a < 0.06, 0, a)
    return Image.fromarray(np.dstack([col, a * 255]).astype(np.uint8), "RGBA")


def ramp(n, frac):
    t = np.clip(np.arange(n) / (n * frac), 0, 1)
    return t * t * (3 - 2 * t)


def foliage():
    out = os.path.join(ROOT, "assets", "fol")
    os.makedirs(out, exist_ok=True)
    for name, (rel, width) in FOLIAGE.items():
        im = cut_white(os.path.join(ART, "foliage", "2026-10-04-white-background-v1", rel))
        im = im.crop(im.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox())
        if im.width > width:
            im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
        if name.startswith("ivy"):
            # the art is cut flat along its top and left edges: fade those so no square block shows
            a = np.asarray(im.getchannel("A")).astype(np.float32) / 255
            a = a * ramp(a.shape[0], .16)[:, None] * ramp(a.shape[1], .12)[None, :]
            im.putalpha(Image.fromarray((a * 255).astype(np.uint8)))
        dst = os.path.join(out, name + ".webp")
        im.save(dst, "WEBP", quality=82, method=6)
        print("%-20s %dx%d %d KB" % (name, im.width, im.height, os.path.getsize(dst) // 1024))


SCENES = {   # slug -> source png under G:\TUR\_art\locations (nine 3:1 panoramas for /scenes/ and the page banners)
    "mountain-lake": r"2026-10-04-highland-basin-v1\highland_basin_v1.png",
    "pink-temple": r"2026-10-04-blossom-grove-temple-v1\temple_of_the_blossom_grove_v1.png",
    "misty-castle": r"2026-10-04-castle-in-the-mists-v1\castle_in_the_mists_v1.png",
    "snow-gorge": r"2026-10-04-frostbound-citadel-v1\frostbound_citadel_v1.png",
    "forest-road": r"2026-10-04-blushwood-road-v1\blushwood_road_v1.png",
    "calm-bay": r"2026-10-04-willow-bay-v1\willow_bay_v1.png",
    "shipwrecks": r"2026-10-04-wreckflower-isle-v1\wreckflower_isle_v1.png",
    "autumn-road": r"2026-10-04-autumn-checkpoint-v1\autumn_checkpoint_v1.png",
    "night-town": r"2026-10-04-midnight-harbor-v1\midnight_harbor_v1.png",
}


def scenes():
    """The panoramas carry no place names anywhere (file names here are neutral on purpose)."""
    out = os.path.join(ROOT, "assets", "scene")
    os.makedirs(out, exist_ok=True)
    for slug, rel in SCENES.items():
        im = Image.open(os.path.join(ART, "locations", rel)).convert("RGB")
        im = im.resize((1600, round(im.height * 1600 / im.width)), Image.LANCZOS)
        dst = os.path.join(out, slug + ".webp")
        im.save(dst, "WEBP", quality=78, method=6)
        print("%-20s %dx%d %d KB" % (slug, im.width, im.height, os.path.getsize(dst) // 1024))


if __name__ == "__main__":
    hubs()
    foliage()
    scenes()
