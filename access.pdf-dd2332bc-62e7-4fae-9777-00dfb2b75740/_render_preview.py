"""Render the first page of a PDF to PNG so the poster layout can be inspected.

Usage:  python _render_preview.py [pdf_file] [out_png] [dpi]
"""
import os
import sys

import fitz  # PyMuPDF

base = os.path.dirname(os.path.abspath(__file__))
pdf = sys.argv[1] if len(sys.argv) > 1 else os.path.join(base, "poster.pdf")
out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(base, "_preview.png")
dpi = int(sys.argv[3]) if len(sys.argv) > 3 else 40

doc = fitz.open(pdf)
print("pages:", doc.page_count)
for probe in (0.28, 0.62, 0.95):
    page = doc[0]
    clip = fitz.Rect(0, probe * 0.01 * page.rect.height,
                     page.rect.width, (probe + 0.34) * page.rect.height)
    pix = page.get_pixmap(dpi=dpi, clip=clip)
    name = out.replace(".png", "_%d.png" % int(probe * 100))
    pix.save(name)
    print("wrote", name, pix.width, "x", pix.height)
