# fix9.py -- poster2 copy expansion part 1: header tagline, KPI line, block 1, block 2
p = 'poster2.tex'
s = open(p, encoding='utf-8').read()
n0 = len(s)
pairs = [
 (r'''cut from \textbf{$-35\%$ to $-7\%$}.}''',
  r'''cut from \textbf{$-35\%$ to $-7\%$}, China's from $-92\%$ to $-47\%$, and no candidate tree is ever thrown away.}'''),
 (r'''Gemma-2-2B, \$0 inference}''',
  r'''Gemma-2-2B, \$0 inference \textbullet\ one monthly rebalance, judged and repaired in minutes}'''),
 (r'''(score 2 or less).''',
  r'''(score 2 or less).
  \item Deletion is expensive: a dropped tree takes its partial signal with it, and a thinner pool converges faster onto one lucky regime.
  \item Local 3B/2B models make the judge cheap enough to call every generation: \$0 API cost, prompts never leave the workstation, latency fits the monthly rebalance.'''),
 (r'''an economic compass.''',
  r'''an economic compass. It drifts over weeks, so one noisy headline never flips the prior.'''),
 (r'''turbulence to reversals + quality.''',
  r'''turbulence to reversals + quality. Baum--Welch learns the transitions; Viterbi decodes today's state once a day.'''),
 (r'''Sharpe minus complexity fitness.''',
  r'''Sharpe minus complexity fitness. The parsimony term prices in every node, so bloat is charged from generation one.'''),
 (r'''Gemma rewrites failures from a closed vocabulary.''',
  r'''Gemma rewrites failures from a closed vocabulary --- at most $L\le5$ typed edits, so a rewrite can never invent a data source that does not exist.'''),
 (r'''\item \hl{Settings:} AFM FinBERT''',
  r'''\item \hl{Guards:} every repaired tree must compile through the AST check and pass validation ranges before it re-enters the pool; a rewrite that fails never replaces its parent.
  \item \hl{Settings:} AFM FinBERT'''),
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
print('fix9 done: %d -> %d bytes, warnings %d' % (n0, len(s), warn))
