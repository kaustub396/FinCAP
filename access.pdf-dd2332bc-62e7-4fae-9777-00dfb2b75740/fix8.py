# fix8.py -- poster2 LAYOUT: drop top TikZ band, widen middle column.
# Columns 0.325/0.345/0.325 -> 0.28/0.435/0.28 (same 0.995 total => no overfull).
p = 'poster2.tex'
s = open(p, encoding='utf-8').read()
n0 = len(s)

# 1) remove the "SYSTEM ARCHITECTURE -- read left to right" block
a = s.find(r'\begin{block}{SYSTEM ARCHITECTURE')
if a >= 0:
    b = s.find(r'\end{block}', a)
    assert b > a, 'band end not found'
    ls = s.rfind('\n', 0, a) + 1
    le = b + len(r'\end{block}')
    if s[le:le + 1] == '\n':
        le += 1
    band = s[ls:le]
    s = s[:ls] + s[le:]
    print('removed top band (%d words)' % len(band.split()))
else:
    print('top band already gone')

# 2) rebalance column widths (bigger middle figure)
c1 = s.count(r'\column{0.325\linewidth}')
c2 = s.count(r'\column{0.345\linewidth}')
s = s.replace(r'\column{0.325\linewidth}', r'\column{0.28\linewidth}')
s = s.replace(r'\column{0.345\linewidth}', r'\column{0.435\linewidth}')
print('side cols replaced: %d | middle col replaced: %d' % (c1, c2))

open(p, 'w', encoding='utf-8').write(s)
print('fix8 done: %d -> %d bytes' % (n0, len(s)))
