"""Locate \\overfullrule marks (small black filled rectangles) drawn by TeX.

Usage: python _overfull.py [poster.pdf]

With \\setlength{\\overfullrule}{4pt} active, every over-full box gets a 4pt
wide black rule at its right edge; finding these tells us which table/paragraph
overflows and by roughly how much (rule width == overflow in points).
"""
import os
import sys

import pymupdf

base = os.path.dirname(os.path.abspath(__file__))
pdf = sys.argv[1] if len(sys.argv) > 1 else os.path.join(base, "poster.pdf")

CM = 72.0 / 2.54
doc = pymupdf.open(pdf)
page = doc[0]
W = page.rect.width

hits = []
for d in page.get_drawings():
    fill = d.get("fill")
    if not fill or max(fill) > 0.25:          # \overfullrule uses the current
        continue                              # text colour (black!88 here)
    r = d["rect"]
    if not (3.0 < r.width < 5.5):             # overfullrule = 4pt wide
        continue
    if r.height < 1.0 or r.height > 800.0:
        continue
    hits.append(r)

print("page width %.1f cm" % (W / CM))
if not hits:
    print("no overfullrule marks found -- no overfull hboxes")
for r in sorted(hits, key=lambda r: (r.y0, r.x0)):
    print("mark  y0=%7.2f  y1=%7.2f (h=%5.2f pt)  x0=%7.2f  x1=%7.2f cm  |  rule width %4.2f pt"
          % (r.y0 / CM, r.y1 / CM, r.height, r.x0 / CM, r.x1 / CM, r.width))
