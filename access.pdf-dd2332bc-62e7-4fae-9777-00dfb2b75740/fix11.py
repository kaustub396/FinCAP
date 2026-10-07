# fix11.py -- poster2 copy expansion part 3: blocks 6, 7, take-away, refs footer
p = 'poster2.tex'
s = open(p, encoding='utf-8').read()
n0 = len(s)
pairs = [
 (r'''about \$250M capacity; costs in; \$0 inference (local 3B/2B models).''',
  r'''about \$250M capacity; 20+10 bps costs priced in, INR 50 Cr cap.'''),
 (r'''\item \hl{Next:} NSE 500''',
  r'''\item \hl{Cheap to run:} one monthly pass on a single workstation --- local 3B/2B models, no cloud API, \$0 inference.
  \item \hl{Where it wins:} decay control --- S\&P keeps 93\% of its backtest Sharpe, SSE keeps about half instead of a tenth.
  \item \hl{Honest limits:} the SSE level (0.067) is still small, and transfer is tested on one US plus one Chinese index.
  \item \hl{Next:} NSE 500'''),
 (r'''sine on prices is noise.''',
  r'''sine on prices is noise: it oscillates with no economic channel, so it fits one window and dies in the next.'''),
 (r'''--- risk-adjusted momentum. Rank IC''',
  r'''--- return scaled by its own trailing volatility: risk-adjusted momentum, the line a quant desk would write by hand. Rank IC'''),
 (r'''regime routing is why wealth survives shocks.''',
  r'''regime routing is why wealth survives shocks. Read together: cleaner operators on top, regime-aware routing below, one smooth equity curve at the end.'''),
 (r'''India to US to China.''',
  r'''India to US to China, at zero inference cost.'''),
 (r'''Draft 1 (poster.pdf) kept as full version.''',
  r'''Draft 1 (poster.pdf) is the full version behind every number shown above.'''),
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
print('fix11 done: %d -> %d bytes, warnings %d' % (n0, len(s), warn))
