"""Make assets/deerisle-land.png: a flat land/water silhouette of Deer Isle.

Source: a reference map screenshot (default G:\\TUR\\TUR_images\\deerisle_map_izurvive.png).
Only the land/water SHAPE is taken from it: every pixel that isn't water becomes one flat
colour, everything else transparent, so the output carries none of the source's artwork.
The reference spans the whole 16384 m world edge to edge (8 grid cells of 2048 m).

    python tools/make_land_mask.py [source.png]
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SITE = Path(__file__).resolve().parents[1]
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"G:\TUR\TUR_images\deerisle_map_izurvive.png")
OUT = SITE / "assets" / "deerisle-land.png"
SIZE = 1024
LAND = (58, 50, 45)             # flat colour; the page tints over it
BORDER = 8                      # px of the source's dark frame to discard


def main():
    im = Image.open(SRC).convert("RGB")
    a = np.asarray(im).astype(int)
    h, w = a.shape[:2]
    # Water is the one big flat colour: the most common colour is the reference, and
    # anything close to it (anti-aliasing, faint grid lines) counts as water too.
    cols, counts = np.unique(a.reshape(-1, 3), axis=0, return_counts=True)
    water = cols[counts.argmax()]
    land = (np.abs(a - water).sum(axis=2) > 60)
    land[:BORDER, :] = land[-BORDER:, :] = False
    land[:, :BORDER] = land[:, -BORDER:] = False
    m = Image.fromarray(land.astype(np.uint8) * 255, "L")
    # Thin things (grid lines, the watermark) go with an open; then flood the ocean
    # from the frame and turn every enclosed hole (labels, roads, marsh stripes) to land.
    m = m.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3))
    sea = m.copy()
    ImageDraw.floodfill(sea, (1, 1), 128, thresh=10)      # ocean becomes 128
    arr = np.asarray(sea)
    filled = np.where(arr == 128, 0, 255).astype(np.uint8)  # ocean -> water, rest -> land
    m = Image.fromarray(filled, "L")
    m = m.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
    m = m.resize((SIZE, SIZE), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.9))
    alpha = np.asarray(m)
    rgba = np.zeros((SIZE, SIZE, 4), np.uint8)
    rgba[..., :3] = LAND
    rgba[..., 3] = alpha
    Image.fromarray(rgba, "RGBA").save(OUT, optimize=True)
    print(f"{OUT}: {SIZE}px, land {(alpha > 127).mean() * 100:.1f}% of the square")


if __name__ == "__main__":
    main()
