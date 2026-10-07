# fix12.py -- poster2 copy expansion part 4: top up to net +50% vs original 810 words
p = 'poster2.tex'
s = open(p, encoding='utf-8').read()
n0 = len(s)
pairs = [
 (r'''\begin{block}{4 Decay cut in half (Sharpe)}''',
  r'''\begin{block}{4 Decay cut in half (Sharpe)}
Out-of-sample Sharpe against the in-sample peak, three engines per market: the more structure that survives the test window, the less Sharpe bleeds away. Conditioning helps, repairing helps more, and together they leave both markets tradable.'''),
 (r'''then build the dollar-neutral book.}''',
  r'''then build the dollar-neutral book.}
\begin{itemize}
  \item \hl{Top-left:} multi-regime data in; GP evolution mines a specialist pool per regime.
  \item \hl{Top-right:} judge, then repair --- the two-stage refiner this poster is about.
  \item \hl{Bottom row:} signals fused with the AFM/HMM state, sized, costs applied, portfolio out.
\end{itemize}'''),
 (r'''latency fits the monthly rebalance.''',
  r'''latency fits the monthly rebalance.
  \item The claim stays narrow on purpose: repair lifts out-of-sample stability, not in-sample fit, and never widens the risk budget.'''),
 (r'''and no candidate tree is ever thrown away.}''',
  r'''and no candidate tree is ever thrown away --- the whole loop costs one monthly pass on a single workstation.}'''),
 (r'''so every repaired formula still reads like something a desk would write.''',
  r'''so every repaired formula still reads like something a desk would write. Because the inputs stay classical, the repair step can never smuggle in data the GP never saw.'''),
 (r'''Wealth 2019--25 compounds through bull + bear (momentum DD $-40.65\%$).''',
  r'''Wealth 2019--25 compounds through bull + bear while a plain momentum book gives back $-40.65\%$ at its worst.'''),
 (r'''stickiness 0.994/0.983.''',
  r'''stickiness 0.994/0.983 --- the model rarely flips states, so the routing signal stays stable.'''),
 (r'''dollar-neutral top/bottom-15\%, monthly rebalance.''',
  r'''dollar-neutral top/bottom-15\%, monthly rebalance. The identical setup runs on Nifty, S\&P and SSE --- nothing is retuned per market.'''),
 (r'''zero crashes over 1,729 days.''',
  r'''zero crashes over 1,729 days. Both edits stay inside the original operator set, so no new primitive has to be back-tested.'''),
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
print('fix12 done: %d -> %d bytes, warnings %d' % (n0, len(s), warn))
