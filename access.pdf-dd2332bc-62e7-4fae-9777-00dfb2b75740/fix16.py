# fix16: enlarge architecture image by widening middle column (0.435 -> 0.505,
# sides 0.28 -> 0.245), and trim Block 3 intro/caption to absorb the extra height.
# Idempotent anchor-based replacement.
import io, sys

PATH = 'poster2.tex'
src = io.open(PATH, encoding='utf-8').read()
orig = src

# 1) Column widths. The two identical 0.28 lines are handled by position:
#    replace the mid one first (unique), then left, then the remaining (right).
a_mid = r'\column{0.435\linewidth}'
b_mid = r'\column{0.505\linewidth}'
if a_mid in src:
    src = src.replace(a_mid, b_mid, 1)
    print('mid column 0.435 -> 0.505')

a_side = r'\column{0.28\linewidth}'
b_side = r'\column{0.245\linewidth}'
n = src.count(a_side)
if n == 2:
    src = src.replace(a_side, b_side)   # both side columns
    print('side columns 0.28 -> 0.245 (2 replaced)')
elif n == 0:
    print('side columns already patched')
else:
    sys.exit('ERROR: unexpected count of 0.28 columns: %d' % n)

# 2) Block 3 intro line -> shorter
a_intro = r'{\normalsize\itshape\color{black!70} Left half mines candidates from data + regimes; the right half repairs --- never deletes --- what the economics judge rejects; the lower panels fuse the signals and execute the portfolio.\par}'
b_intro = r'{\normalsize\itshape\color{black!70} Left: mine candidates from data + regimes. Right: repair --- never delete --- what the judge rejects. Lower: fuse, size, execute.\par}'
if a_intro in src:
    src = src.replace(a_intro, b_intro, 1)
    print('block 3 intro shortened')
elif b_intro in src:
    print('block 3 intro already shortened')
else:
    sys.exit('ERROR: block 3 intro anchor not found')

# 3) Block 3 figure caption -> shorter
a_cap = r'\figcap{Figure 1. Dual two-stage framework: (1) regime-aware factor engine (AFM macro + HMM states + regime GP) and (2) post-evolution Two-Stage LLM Refiner (Llama-3B judge, Gemma-2B closed-vocab repair) with AST + validation guards. The four quadrants walk the same path as the numbers below: mine, judge, repair, then build the dollar-neutral book.}'
b_cap = r'\figcap{Figure 1. Dual two-stage framework: (1) regime-aware factor engine (AFM macro + HMM states + regime GP); (2) Two-Stage LLM Refiner (Llama-3B judge, Gemma-2B closed-vocab repair) behind AST + validation guards --- mine, judge, repair, then build the dollar-neutral book.}'
if a_cap in src:
    src = src.replace(a_cap, b_cap, 1)
    print('block 3 caption shortened')
elif b_cap in src:
    print('block 3 caption already shortened')
else:
    sys.exit('ERROR: block 3 caption anchor not found')

if src != orig:
    io.open(PATH, 'w', encoding='utf-8', newline='').write(src)
    print('written', PATH)
else:
    print('no changes (already applied)')
