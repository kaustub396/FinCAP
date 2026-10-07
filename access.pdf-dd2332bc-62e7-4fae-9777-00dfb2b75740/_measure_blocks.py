"""List the poster block title bars (navy rectangles) with their positions.

Usage: python _measure_blocks.py [poster.pdf]
Prints one line per block: column, top y (cm), bottom y (cm), height (cm).
"""
import os
import sys

import pymupdf

base = os.path.dirname(os.path.abspath(__file__))
pdf = sys.argv[1] if len(sys.argv) > 1 else os.path.join(base, "poster.pdf")

doc = pymupdf.open(pdf)
page = doc[0]
H, W = page.rect.height, page.rect.width
CM = 72.0 / 2.54
NAVY = (14 / 255.0, 42 / 255.0, 71 / 255.0)

x0, x1 = 1.0 * CM, W - 1.0 * CM
bodies = [x0 + i * (x1 - x0) / 3.0 for i in range(4)]

bars = []
for d in page.get_drawings():
    fill = d.get("fill")
    if not fill:
        continue
    if max(abs(fill[i] - NAVY[i]) for i in range(3)) > 0.04:
        continue
    r = d["rect"]
    if r.width < 4 * CM or r.height > 4 * CM:
        continue
    bars.append(r)

bars.sort(key=lambda r: (r.y0, r.x0))
prev_bottom = [0.0, 0.0, 0.0]
for r in bars:
    col = 0
    for i in range(3):
        if r.x0 >= bodies[i] - 4 and r.x0 < bodies[i + 1] - 4:
            col = i
    print("col %d | bar top %6.1f cm  bottom %6.1f cm | height %5.1f cm | gap from previous end: %5.1f cm"
          % (col + 1, r.y0 / CM, r.y1 / CM, r.height / CM, (r.y0 - prev_bottom[col]) / CM))
