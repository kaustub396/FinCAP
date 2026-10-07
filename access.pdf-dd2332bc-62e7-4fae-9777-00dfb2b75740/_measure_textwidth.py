"""Measure the *effective* text width inside every poster block.

Usage: python _measure_textwidth.py [poster.pdf]

For each navy block title bar (== the block's outer box) this prints the
leftmost / rightmost extent of the text lines inside that block, so the real
paragraph width (\\hsize) can be derived and compared with \\linewidth.
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

bars = []
for d in page.get_drawings():
    f = d.get("fill")
    if not f or max(abs(f[i] - NAVY[i]) for i in range(3)) > 0.04:
        continue
    r = d["rect"]
    if r.width < 4 * CM or r.height > 4 * CM:
        continue
    bars.append(r)
bars.sort(key=lambda r: (r.x0, r.y0))

lines = []
for blk in page.get_text("dict")["blocks"]:
    if blk.get("type") != 0:
        continue
    for ln in blk["lines"]:
        xs = [sp["bbox"][0] for sp in ln["spans"] if sp["text"].strip()]
        xe = [sp["bbox"][2] for sp in ln["spans"] if sp["text"].strip()]
        if xs:
            lines.append((min(xs), max(xe), (ln["bbox"][1] + ln["bbox"][3]) / 2))

for i, bar in enumerate(bars):
    same_col = [b for b in bars if abs(b.x0 - bar.x0) < 2]
    nxt = min([b.y0 for b in same_col if b.y0 > bar.y0 + 1] or [page.rect.height])
    sel = [(x0, x1, y) for x0, x1, y in lines
           if bar.y1 < y < nxt and x0 > bar.x0 - 40 and x1 < bar.x1 + 40]
    if not sel:
        continue
    mn = min(x for x, _, _ in sel)
    mx = max(x for _, x, _ in sel)
    print("box x %6.2f-%6.2f y %6.1f-%6.1f | text x %6.2f-%6.2f | left pad %.2f  right pad %.2f  -> text width %5.2f cm"
          % (bar.x0 / CM, bar.x1 / CM, bar.y0 / CM, nxt / CM, mn / CM, mx / CM,
             (mn - bar.x0) / CM, (bar.x1 - mx) / CM, (mx - mn) / CM))
