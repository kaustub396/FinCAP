# fix10.py -- poster2 copy expansion part 2: blocks 2b, 3, 4, 5
p = 'poster2.tex'
s = open(p, encoding='utf-8').read()
n0 = len(s)
pairs = [
 (r'''recompile, back into evolution. Zero attrition: every repair compiles.''',
  r'''recompile, back into evolution. Trees scoring 3--5 pass untouched, so the editor spends compute only where the economics is broken. Zero attrition: every repair compiles, the pool never drops below its 500 trees, and nothing is discarded for looking unusual --- only for scoring low.'''),
 (r'''Regime specialists, not one average model.''',
  r'''Regime specialists, not one average model: every rolling window is judged on its own regime, so a calm 2013--16 never has to average out a hostile 2017--20.'''),
 (r'''\includegraphics[width=\linewidth,keepaspectratio]{images/38de923ab8b5dcfc8845af49392f1122074f030c0adba45a84530c30bf42c1bf.jpg}''',
  r'''{\normalsize\itshape\color{black!70} Left half mines candidates from data + regimes; the right half repairs --- never deletes --- what the economics judge rejects; the lower panels fuse the signals and execute the portfolio.\par}
\vspace{0.25cm}
\includegraphics[width=\linewidth,keepaspectratio]{images/38de923ab8b5dcfc8845af49392f1122074f030c0adba45a84530c30bf42c1bf.jpg}'''),
 (r'''with AST + validation guards.}''',
  r'''with AST + validation guards. The four quadrants walk the same path as the numbers below: mine, judge, repair, then build the dollar-neutral book.}'''),
 (r'''Repair removes overfit noise instead of deleting trees.''',
  r'''Vanilla GP overfits its training window, conditioning on the regime removes part of the damage, and semantic repair removes the rest --- all without deleting trees. On the SSE the level (0.067) stays small, so the honest claim there is halved decay, not a large Sharpe.'''),
 (r'''Sensible economics: trends in calm markets, reversals + quality in stress.''',
  r'''Each bar counts appearances of that feature in the top-ranked formulas: a trend term you can hold in calm regimes plus a scaler that trims size when vol rises, with reversals + quality for stress. The categories stay classical (trend, momentum, volatility, quality), so every repaired formula still reads like something a desk would write.'''),
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
print('fix10 done: %d -> %d bytes, warnings %d' % (n0, len(s), warn))
