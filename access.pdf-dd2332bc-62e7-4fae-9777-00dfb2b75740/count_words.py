import re, sys
p = sys.argv[1] if len(sys.argv) > 1 else 'poster2.tex'
s = open(p, encoding='utf-8').read()
i = s.find('\\begin{document}')
b = s[i:] if i != -1 else s
words = [t for t in re.split(r'\s+', b)
         if re.search(r'[A-Za-z0-9]', t)
         and not t.startswith('\\begin')
         and not t.startswith('\\end')]
print(p, 'body words:', len(words))
