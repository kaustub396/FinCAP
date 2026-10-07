# fix13.py -- move block 2b (Loop + stability) from left column to top of middle column.
# Left column was overflowing past the page bottom (refs footer pushed off-page);
# middle column had a ~1400pt hole. Image width rescaled for the wider column.
p = 'poster2.tex'
s = open(p, encoding='utf-8').read()
i_col = s.find(r'\column{0.435\linewidth}')
i2 = s.find(r'\begin{block}{2b Loop + stability')
i3 = s.find(r'\begin{block}{3 System architecture')
if i2 > i_col > 0 and i3 > 0:
    print('2b already in middle column -- nothing to do')
else:
    assert i2 > 0 and i3 > 0 and i_col > 0, 'anchors not found'
    ls = s.rfind('\n', 0, i2) + 1
    le = s.find(r'\end{block}', i2) + len(r'\end{block}')
    if s[le:le + 1] == '\n':
        le += 1
    blk = s[ls:le]
    s = s[:ls] + s[le:]
    blk = blk.replace(r'width=0.92\linewidth', r'width=0.6\linewidth')
    j = s.find(r'\begin{block}{3 System architecture')
    js = s.rfind('\n', 0, j) + 1
    s = s[:js] + blk + s[js:]
    print('moved 2b into middle column (%d chars, image w=%.1f%%)'
          % (len(blk), 60))
open(p, 'w', encoding='utf-8').write(s)
print('fix13 done')
