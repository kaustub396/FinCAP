"""Measure how far down the page each poster column extends.

Usage: python _measure_columns.py [poster.pdf]
Prints the bottom (in cm) of the content of each of the three columns, so
column over/under-flow can be corrected precisely.
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

# content region (beamerposter: hmargin 1cm on an A0 portrait page)
x0, x1 = 1.0 * CM, W - 1.0 * CM
bodies = [x0 + i * (x1 - x0) / 3.0 for i in range(4)]

drawn = [0.0, 0.0, 0.0]
for item in page.get_text("blocks"):
    bx0, by0, bx1, by1 = item[:4]
    for i in range(3):
        if bx0 >= bodies[i] - 2 and bx1 <= bodies[i + 1] + 2:
            drawn[i] = max(drawn[i], by1)
            break
for item in page.get_drawings():
    r = item["rect"]
    for i in range(3):
        if r.x0 >= bodies[i] - 2 and r.x1 <= bodies[i + 1] + 2:
            drawn[i] = max(drawn[i], r.y1)
            break
for info in page.get_image_info():
    r = pymupdf.Rect(info["bbox"])
    for i in range(3):
        if r.x0 >= bodies[i] - 2 and r.x1 <= bodies[i + 1] + 2:
            drawn[i] = max(drawn[i], r.y1)
            break

print("page height: %.1f cm  (usable text height ~118.9 cm)" % (H / CM))
for i, bottom in enumerate(drawn):
    print("column %d: content bottom = %6.1f cm   (slack = %+6.1f cm)"
          % (i + 1, bottom / CM, (H - bottom) / CM))
