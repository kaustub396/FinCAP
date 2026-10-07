import io
SRC='poster2_land.tex'
t=io.open(SRC,encoding='utf-8').read()
BS='\\begin{block}{4 Decay cut'
i0=t.find(BS)
assert i0!=-1
j0=t.find('\\end{block}',i0)+len('\\end{block}')
b4=t[i0-1:j0]
t=t[:i0-1]+t[j0:]
anchor='\\end{block}\n\\column{0.505'
assert anchor in t, 'anchor missing'
t=t.replace(anchor, '\\end{block}\n'+b4+'\n\\column{0.505',1)
io.open(SRC,'w',encoding='utf-8',newline='').write(t)
print('moved B4, len',len(b4))
