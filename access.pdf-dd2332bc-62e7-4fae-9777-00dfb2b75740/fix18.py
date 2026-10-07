# fix18: generate a LANDSCAPE-orientation variant of the poster (poster2_land.tex)
# from poster2.tex, so the middle column -- and with it the architecture figure --
# becomes much wider (landscape A0 = 3370 x 2384 pt).
# Idempotent: always regenerated from poster2.tex (edit poster2.tex, re-run this).
#
# Stage 2 -- make the content FIT the shorter landscape columns without losing
# body text: tighter fixed spacing, font scale 0.98 -> 0.90, smaller secondary
# chart. Measured overflow was ~1250 pt total (mid 755, right 511); these
# levers recover ~950 pt, the rest comes from the word trims in stage 3.
import io

SRC = 'poster2.tex'
DST = 'poster2_land.tex'

src = io.open(SRC, encoding='utf-8').read()

# --- stage 1: orientation + font scale -----------------------------------
old = r'\usepackage[orientation=portrait, size=a0, scale=0.98]{beamerposter}'
new = r'\usepackage[orientation=landscape, size=a0, scale=0.84]{beamerposter}'
if old not in src:
    raise SystemExit('ERROR: beamerposter portrait line not found')
src = src.replace(old, new, 1)

# --- stage 2: fixed spacings + secondary chart (landscape-only) ----------
PAIRS = [
    # body paragraph spacing
    (r'\setlength{\parskip}{0.28cm}\justifying%',
     r'\setlength{\parskip}{0.10cm}\justifying%'),
    # list item spacing
    (r'\setbeamertemplate{itemize/enumerate body begin}{\setlength{\itemsep}{0.25cm}}',
     r'\setbeamertemplate{itemize/enumerate body begin}{\setlength{\itemsep}{0.06cm}}'),
    # block top/bottom padding
    (r'\par\vskip0.55cm%',
     r'\par\vskip0.28cm%'),
    (r'\setbeamertemplate{block end}{\end{beamercolorbox}\vspace*{0.15cm}}',
     r'\setbeamertemplate{block end}{\end{beamercolorbox}\vspace*{0.05cm}}'),
    # block 2b rolling-Sharpe chart: secondary figure, shrink to buy height
    (r'\includegraphics[width=0.6\linewidth,keepaspectratio]{images/28656a9cc9f26a4ffd2ce0ab7611324d8cd0fff6192ee9abf348a58dd50cc0a7.jpg}',
     r'\includegraphics[width=0.30\linewidth,keepaspectratio]{images/28656a9cc9f26a4ffd2ce0ab7611324d8cd0fff6192ee9abf348a58dd50cc0a7.jpg}'),
    # HERO figure (block 3, mid column): tallest element; 0.66 keeps labels legible
    (r'\includegraphics[width=\linewidth,keepaspectratio]{images/38de923a',
     r'\includegraphics[width=0.66\linewidth,keepaspectratio]{images/38de923a'),
    # Block 5 feature-mix chart (right column)
    (r'\includegraphics[width=0.92\linewidth,keepaspectratio]{images/97b82991',
     r'\includegraphics[width=0.62\linewidth,keepaspectratio]{images/97b82991'),
]

for old_s, new_s in PAIRS:
    if old_s not in src:
        raise SystemExit('ERROR: anchor not found: %r' % old_s[:70])
    src = src.replace(old_s, new_s, 1)

# --- stage 3: word trims that are redundant with neighbouring text -------
# (filled in as measurements demand; anchors asserted, skipped if absent)
TRIMS = [
    # Block 3: the three bullets repeat the italic intro + caption one line
    # above/below the figure; drop them in the tight landscape layout.
    (r'''\begin{itemize}
  \item \hl{Top-left:} multi-regime data in; GP evolution mines a specialist pool per regime.
  \item \hl{Top-right:} judge, then repair --- the two-stage refiner this poster is about.
  \item \hl{Bottom row:} signals fused with the AFM/HMM state, sized, costs applied, portfolio out.
\end{itemize}
''', ''),
]

for old_s, new_s in TRIMS:
    if old_s in src:
        src = src.replace(old_s, new_s, 1)
        print('trim applied:', new_s[:0] + old_s.splitlines()[1][:50])
    else:
        print('trim already applied or missing:', old_s.splitlines()[1][:50])

io.open(DST, 'w', encoding='utf-8', newline='').write(src)
print('written', DST)

