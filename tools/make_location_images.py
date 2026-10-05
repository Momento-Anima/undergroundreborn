"""Builds the Locations / Scenes page art:
  assets/loc/*.webp    six trader-hub images
  assets/scene/*.webp  nine 3:1 panoramas + the night grove panorama (gallery and page banners)
  assets/sak/*.webp    sakura branches, petal sprite sheet, fireflies, petal moss strip

Source art is NOT in this repo. It lives on Momento's PC (read-only, never modified):
  G:\\TUR\\_art\\locations\\<date>-<hub>-v<N>\\<file>.png                  the hub and panorama images
  G:\\TUR\\_art\\foliage\\2026-10-04-sakura-fireflies-v1\\*.png             sakura pieces (on white, fireflies on black)

Run: python tools/make_location_images.py     (needs Pillow and numpy)
Groot's Hill uses its v2 (exterior) image; the others use v1.
File names are descriptive on purpose: working titles of unidentified places are never used on the site.
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = r"G:\TUR\_art"
SAKURA = os.path.join(ART, "foliage", "2026-10-04-sakura-fireflies-v1")

HUBS = {   # slug -> source png under G:\TUR\_art\locations
    "groots-hill": r"2026-10-04-groots-hill-market-v2\groots_hill_market_exterior_v2.png",
    "waldoboro": r"2026-10-04-waldoboro-trading-post-v1\waldoboro_trading_post_aerial_v1.png",
    "ship-hole-harbor": r"2026-10-04-ship-hole-harbor-v1\ship_hole_harbor_aerial_v1.png",
    "sons-of-deer-isle": r"2026-10-04-sons-of-deer-isle-v1\sons_of_deer_isle_aerial_v1.png",
    "grey-market": r"2026-10-04-grey-market-v1\grey_market_aerial_v1.png",
    "collectibles-trader": r"2026-10-04-collectibles-trader-v1\collectibles_trader_aerial_v1.png",
}
SCENES = {   # slug -> source png under G:\TUR\_art\locations
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


def panorama(src, dst):
    im = Image.open(src).convert("RGB")
    im = im.resize((1600, round(im.height * 1600 / im.width)), Image.LANCZOS)
    im.save(dst, "WEBP", quality=78, method=6)
    print("%-20s %dx%d %d KB" % (os.path.basename(dst)[:-5], im.width, im.height, os.path.getsize(dst) // 1024))


def scenes():
    out = os.path.join(ROOT, "assets", "scene")
    os.makedirs(out, exist_ok=True)
    for slug, rel in SCENES.items():
        panorama(os.path.join(ART, "locations", rel), os.path.join(out, slug + ".webp"))
    panorama(os.path.join(SAKURA, "04_sakura_firefly_night_panorama.png"), os.path.join(out, "night-grove.webp"))


def cut_white(path):
    """Remove the white backdrop: soft alpha from the distance to white, then un-mix the white halo."""
    rgb = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    a = np.clip((255.0 - rgb.min(axis=2) - T0) / (T1 - T0), 0, 1)
    af = np.maximum(a, 1e-3)[..., None]
    col = np.clip((rgb - 255.0 * (1 - af)) / af, 0, 255)
    col = np.where(a[..., None] > 0.999, rgb, col)
    a = np.where(a < 0.06, 0, a)
    return Image.fromarray(np.dstack([col, a * 255]).astype(np.uint8), "RGBA")


def cut_flood(path):
    """For pale objects (petals): clear only the white that connects to the corner, keep petal colour solid."""
    rgb = Image.open(path).convert("RGB")
    arr = np.asarray(rgb).astype(np.int16)
    near_white = (255 - arr.min(axis=2)) < 16
    m = Image.fromarray((near_white * 255).astype(np.uint8), "L").convert("RGB")
    ImageDraw.floodfill(m, (0, 0), (255, 0, 0), thresh=0)       # RGB mode: L mode does not fill
    ma = np.asarray(m)
    bg = (ma[..., 0] == 255) & (ma[..., 1] == 0)
    a = Image.fromarray(np.where(bg, 0, 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(1.1))
    out = rgb.convert("RGBA")
    out.putalpha(a)
    return out


def ramp(n, frac):
    t = np.clip(np.arange(n) / (n * frac), 0, 1)
    return t * t * (3 - 2 * t)


def bbox_crop(im):
    return im.crop(im.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox())


def sakura():
    out = os.path.join(ROOT, "assets", "sak")
    os.makedirs(out, exist_ok=True)

    def save(im, name, q=82):
        p = os.path.join(out, name)
        im.save(p, "WEBP", quality=q, method=6)
        print("%-20s %dx%d %d KB" % (name, im.width, im.height, os.path.getsize(p) // 1024))

    # corner branches: the art is cut flat along its top and left edges, so fade those (no square block shows)
    for src, name in (("01_sakura_branch_v1.png", "branch-a.webp"), ("01_sakura_branch_v3.png", "branch-b.webp")):
        im = bbox_crop(cut_white(os.path.join(SAKURA, src)))
        im = im.resize((900, round(im.height * 900 / im.width)), Image.LANCZOS)
        a = np.asarray(im.getchannel("A")).astype(np.float32) / 255
        a = a * ramp(a.shape[0], .10)[:, None] * ramp(a.shape[1], .08)[None, :]
        im.putalpha(Image.fromarray((a * 255).astype(np.uint8)))
        save(im, name)

    # petals: 4x3 grid on the sheet -> twelve 128 px cells in one sprite (the page script uses nine clean single petals)
    sheet = cut_flood(os.path.join(SAKURA, "02_sakura_petals.png"))
    W, H = sheet.size
    cw, ch = W // 4, H // 3
    sprite = Image.new("RGBA", (512, 384), (0, 0, 0, 0))
    for i in range(12):
        r, c = divmod(i, 4)
        cell = bbox_crop(sheet.crop((c * cw, r * ch, (c + 1) * cw, (r + 1) * ch)))
        cell.thumbnail((118, 118), Image.LANCZOS)
        sprite.alpha_composite(cell, (c * 128 + (128 - cell.width) // 2, r * 128 + (128 - cell.height) // 2))
    save(sprite, "petals.webp", 88)

    # fireflies: used as-is on black with mix-blend-mode: screen
    save(Image.open(os.path.join(SAKURA, "03_fireflies_black.png")).convert("RGB").resize((1200, 900), Image.LANCZOS),
         "fireflies.webp", 80)

    # petal-covered moss strip for the end of the page
    moss = bbox_crop(cut_white(os.path.join(SAKURA, "05_moss_sakura_petal_strip.png")))
    save(moss.resize((1800, round(moss.height * 1800 / moss.width)), Image.LANCZOS), "moss-sakura.webp")


DTF = {   # slug -> source png under G:\TUR\_art\ (Defend the Flag places + the guarded loot crate picture, 16:9)
    "starks-castle": r"dtf\2026-10-04-starks-castle-v1\starks-castle_v1.png",
    "pear-plantation": r"dtf\2026-10-04-pear-plantation-v1\pear-plantation_v1.png",
    "waldoboro-hills-elementary": r"dtf\2026-10-04-waldoboro-elementary-school-v2\waldoboro-elementary-school_v2.png",   # v2 = with the horde, like the others
    "portland-shipping-yard": r"dtf\2026-10-04-portland-shipping-yard-v1\portland-shipping-yard_v1.png",
    "warren-cove-cemetery": r"dtf\2026-10-04-warren-cove-cemetery-v1\warren-cove-cemetery_v1.png",
    "loot-crate": r"loot-crate\2026-10-05-loot-crate-v1\loot-crate_v1.png",
    # still to come: asheville-ruins, old-town-castle, racetrack-roundup, proving-grounds (art not made yet)
}


def dtf():
    out = os.path.join(ROOT, "assets", "dtf")
    os.makedirs(out, exist_ok=True)
    for slug, rel in DTF.items():
        im = Image.open(os.path.join(ART, rel)).convert("RGB")
        im = im.resize((1200, round(im.height * 1200 / im.width)), Image.LANCZOS)
        dst = os.path.join(out, slug + ".webp")
        im.save(dst, "WEBP", quality=80, method=6)
        print("%-28s %dx%d %d KB" % (slug, im.width, im.height, os.path.getsize(dst) // 1024))


if __name__ == "__main__":
    hubs()
    scenes()
    sakura()
    dtf()
