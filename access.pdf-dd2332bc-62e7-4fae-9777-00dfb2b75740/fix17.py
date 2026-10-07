# fix17: add a small gap between Block 4's intro paragraph and the booktabs
# table minipage -- the top rule currently touches the last text line and
# looks like a stray underline. Idempotent.
import io, sys

PATH = 'poster2.tex'
src = io.open(PATH, encoding='utf-8').read()

if 'tradable.\\par\\vspace{0.3cm}' in src:
    print('block 4 gap already present')
elif 'markets tradable.' in src:
    src = src.replace('markets tradable.', 'markets tradable.\\par\\vspace{0.3cm}', 1)
    io.open(PATH, 'w', encoding='utf-8', newline='').write(src)
    print('block 4: gap added before table minipage')
else:
    sys.exit('ERROR: anchor "markets tradable." not found')
