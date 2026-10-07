# fix14.py -- poster2: separate paragraph/image/caption in blocks 2b, 3, 5
# (without an explicit \par the figcap flowed onto the same line as the image)
p = 'poster2.tex'
s = open(p, encoding='utf-8').read()
n0 = len(s)
pairs = [
 (r'''\centering
\includegraphics[width=0.6\linewidth,keepaspectratio]{images/28656a9cc9f26a4ffd2ce0ab7611324d8cd0fff6192ee9abf348a58dd50cc0a7.jpg}
\figcap{''',
  r'''\par\centering
\includegraphics[width=0.6\linewidth,keepaspectratio]{images/28656a9cc9f26a4ffd2ce0ab7611324d8cd0fff6192ee9abf348a58dd50cc0a7.jpg}
\par\figcap{'''),
 (r'''\includegraphics[width=0.92\linewidth,keepaspectratio]{images/97b82991ea2743e616388671ed37ff6bea3cc310277e70b8b60047cb29f427af.jpg}
\figcap{''',
  r'''\includegraphics[width=0.92\linewidth,keepaspectratio]{images/97b82991ea2743e616388671ed37ff6bea3cc310277e70b8b60047cb29f427af.jpg}
\par\figcap{'''),
 (r'''\includegraphics[width=\linewidth,keepaspectratio]{images/38de923ab8b5dcfc8845af49392f1122074f030c0adba45a84530c30bf42c1bf.jpg}
\figcap{''',
  r'''\includegraphics[width=\linewidth,keepaspectratio]{images/38de923ab8b5dcfc8845af49392f1122074f030c0adba45a84530c30bf42c1bf.jpg}
\par\figcap{'''),
]
warn = 0
for old, new in pairs:
    c = s.count(old)
    if c == 1:
        s = s.replace(old, new)
    else:
        print('WARN count=%d anchor=%.55r' % (c, old))
        warn += 1
open(p, 'w', encoding='utf-8').write(s)
print('fix14 done: %d -> %d bytes, warnings %d' % (n0, len(s), warn))
