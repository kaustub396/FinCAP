"""Detailed layout diagnostic for the A0 poster.

Usage: python _diagnose.py [poster.pdf]

Prints:
  * the vertical extents of the full-width banner boxes (title bar, metric strip,
    footer) -- identified by drawing rectangles spanning the whole text width;
  * for each of the three columns, the bottom of the last item *excluding* the
    full-width footer (so the real column bottom is visible even when the footer
    is pushed off the page).
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

x0, x1 = 1.0 * CM, W - 1.0 * CM
bodies = [x0 + i * (x1 - x0) / 3.0 for i in range(4)]
COLS = ["col 1", "col 2", "col 3"]


def col_of(r):
    for i in range(3):
        if r.x0 >= bodies[i] - 2 and r.x1 <= bodies[i + 1] + 2:
            return i
    return None


items = []
for it in page.get_text("blocks"):
    items.append(("text", pymupdf.Rect(it[:4])))
for it in page.get_drawings():
    items.append(("draw", it["rect"]))
for it in page.get_image_info():
    items.append(("img", pymupdf.Rect(it["bbox"])))

print("page: %.2f x %.2f cm" % (W / CM, H / CM))

# ---- full width banner boxes -----------------------------------------
print("\nfull-width boxes (>= 60 cm wide):")
bands = []
for kind, r in items:
    if kind == "draw" and r.width > 60 * CM and r.height > 0.4 * CM:
        bands.append(r)
for r in sorted(bands, key=lambda r: r.y0):
    print("   y0=%7.2f  y1=%7.2f  (h=%5.2f cm)  x0=%.1f x1=%.1f"
          % (r.y0 / CM, r.y1 / CM, r.height / CM, r.x0 / CM, r.x1 / CM))

# ---- footer:text pushed below the page? ------------------------------
print("\ntext lines whose bottom is inside the last 3 cm of the page:")
for kind, r in items:
    if kind == "text" and r.y1 > H - 3 * CM:
        print("   y0=%7.2f  y1=%7.2f  x0=%.1f x1=%.1f" % (r.y0 / CM, r.y1 / CM, r.x0 / CM, r.x1 / CM))

# ---- per-column bottoms, excluding full-width footer -----------------
footer_top = min((r.y0 for r in bands if r.y0 > 100 * CM), default=H)
print("\nfooter band starts at %.2f cm" % (footer_top / CM))
drawn = [0.0, 0.0, 0.0]
for kind, r in items:
    if r.y0 > footer_top - 1:
        continue  # footer and anything after it
    c = col_of(r)
    if c is not None:
        drawn[c] = max(drawn[c], r.y1)
for i, bottom in enumerate(drawn):
    print("%s: content bottom = %6.2f cm" % (COLS[i], bottom / CM))
