# fix15.py -- poster2: avoid ugly mid-word title breaks in narrow side columns
p = 'poster2.tex'
s = open(p, encoding='utf-8').read()
n0 = len(s)
pairs = [
 (r'''\begin{block}{5 What the machine rediscovers (feature mix)}''',
  r'''\begin{block}{5 What the machine rediscovers (\mbox{feature} mix)}'''),
 (r'''\begin{block}{6 Read this and leave (5-min summary)}''',
  r'''\begin{block}{6 Read this and leave (5-min \mbox{summary})}'''),
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
print('fix15 done: %d -> %d bytes, warnings %d' % (n0, len(s), warn))
