"""Dump the horizontal geometry of every poster block.

Usage: python _layout_dump.py [poster.pdf]

For each navy block title bar it prints the bar extent (== the block box width),
the body panel extent, and how far right the text/images inside the block
actually reach, so rigid content (tables, \\rule, boxes) that sticks out of the
body can be spotted immediately.
"""
import os
import sys

import pymupdf

base = os.path.dirname(os.path.abspath(__file__))
pdf = sys.argv[1] if len(sys.argv) > 1 else os.path.join(base, "poster.pdf")

CM = 72.0 / 2.54
NAVY = (14 / 255.0, 42 / 255.0, 71 / 255.0)

doc = pymupdf.open(pdf)
page = doc[0]
H = page.rect.height

bars = []
for d in page.get_drawings():
    f = d.get("fill")
    if not f or max(abs(f[i] - NAVY[i]) for i in range(3)) > 0.04:
        continue
    r = d["rect"]
    if r.width < 4 * CM or r.height > 4 * CM:
        continue
    bars.append(r)
bars.sort(key=lambda r: (r.y0, r.x0))

texts = [pymupdf.Rect(b[:4]) for b in page.get_text("blocks")]
draws = [d["rect"] for d in page.get_drawings()
         if d.get("fill") or d.get("color")]
imgs = [pymupdf.Rect(i["bbox"]) for i in page.get_image_info()]

print("page: %.1f x %.1f cm" % (page.rect.width / CM, H / CM))
for i, bar in enumerate(bars):
    nxt = bars[i + 1].y0 - 1 if i + 1 < len(bars) else H
    if i + 1 < len(bars) and bars[i + 1].x0 != bar.x0:
        nxt = min(nxt, H)
    y0, y1 = bar.y1 + 1, nxt
    inside = lambda r: r.y0 >= bar.y0 - 1 and r.y1 <= y1 and r.x0 >= bar.x0 - 40 and r.x1 <= bar.x1 + 40
    tx = [r for r in texts if inside(r)]
    dx = [r for r in draws if inside(r)]
    ix = [r for r in imgs if inside(r)]
    tmax = max([r.x1 for r in tx], default=0)
    imax = max([r.x1 for r in ix], default=0)
    print("bar y %6.1f-%6.1f  x %6.2f-%6.2f (w=%5.2f)  |  max text x1 %6.2f  max img x1 %6.2f  (over by %5.2f cm)"
          % (bar.y0 / CM, bar.y1 / CM, bar.x0 / CM, bar.x1 / CM, bar.width / CM,
             tmax / CM, imax / CM, (max(tmax, imax) - bar.x1) / CM))
