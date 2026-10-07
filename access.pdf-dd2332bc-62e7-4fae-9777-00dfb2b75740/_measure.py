"""Measure poster PDF: page size, image rects, column bottoms, refs footer.

Usage: python _measure.py poster2_land.pdf
Column split points are derived from the middle-column x range.
"""
import os
import sys

import pymupdf

base = os.path.dirname(os.path.abspath(__file__))
pdf = sys.argv[1] if len(sys.argv) > 1 else os.path.join(base, "poster.pdf")
doc = pymupdf.open(pdf)
page = doc[0]
W, H = page.rect.width, page.rect.height
print("page %.0f x %.0f pt" % (W, H))

# --- image rectangles (figure sizes) -------------------------------------
for xref in {i[0] for i in page.get_images(full=True)}:
    for r in page.get_image_rects(xref):
        if r.width > 300:
            print("image xref %3d  %4.0f x %4.0f pt  at (%.0f, %.0f)"
                  % (xref, r.width, r.height, r.x0, r.y0))

# --- column bottoms -------------------------------------------------------
# clip beyond the page: overfull content is drawn below the mediabox
blocks = page.get_text("blocks", clip=pymupdf.Rect(-10, -10, W + 10, H + 2000))
refs = [b for b in blocks if "Refs:" in b[4]]
if refs:
    print("refs box  y %.0f-%.0f" % (refs[0][1], refs[0][3]))
else:
    print("refs box  NOT FOUND")

# middle column x range from its block title
mid_title = [b for b in blocks if b[4].startswith("3 System architecture")]
if mid_title:
    xlo = mid_title[0][0] - 10
    print("mid column starts x %.0f" % xlo)
else:
    xlo = W / 3

cols = {"left": [], "mid": [], "right": []}
for b in blocks:
    if b in refs:
        continue
    cx = (b[0] + b[2]) / 2
    if cx < xlo:
        cols["left"].append(b)
    elif cx < xlo + 0.505 * (W - 57) + 40:
        cols["mid"].append(b)
    else:
        cols["right"].append(b)

# image rects count toward column bottoms too
imgs = []
for xref in {i[0] for i in page.get_images(full=True)}:
    for r in page.get_image_rects(xref):
        if r.width > 200:
            imgs.append(r)

for name, col in cols.items():
    if not col:
        print(name, "EMPTY")
        continue
    limit = 2199.0  # refs box must start ~col_bottom+20 and end <= H-145
    bottoms = sorted(col, key=lambda b: -b[3])[:3]
    ext = [r.y1 for r in imgs
           if (r.x0 + r.x1) / 2 >= (xlo if name == "mid" else
                                    (-1 if name == "left" else 1e9))
           or True]
    m = max(col, key=lambda b: b[3])
    ib = max([r.y1 for r in imgs
              if (name == "left" and (r.x0 + r.x1) / 2 < xlo)
              or (name == "mid" and xlo <= (r.x0 + r.x1) / 2 < xlo + 0.505 * (W - 57) + 40)
              or (name == "right" and (r.x0 + r.x1) / 2 >= xlo + 0.505 * (W - 57) + 40)]
             or [0])
    print("%-6s bottom %6.1f (img bottom %5.0f) limit %.0f  -> %s"
          % (name, max(m[3], ib), ib, limit,
             "OVER by %.0f" % (max(m[3], ib) - limit) if max(m[3], ib) > limit else "fits"))
    for b in bottoms:
        print("        y1=%6.1f  %r" % (b[3], b[4][:64].replace("\n", " ")))

