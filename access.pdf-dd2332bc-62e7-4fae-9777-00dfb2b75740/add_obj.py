import io
p='poster2_land.tex'
t=io.open(p,encoding='utf-8').read()
old=r'\begin{block}{1 Problem in 30 seconds}'
new=(r'\begin{block}{0 Objectives}'+'\n'+r'\begin{itemize}'+'\n'
+r'  \item \hl{Primary:} discover symbolic ranking formulas that maximise forward risk-adjusted return across regimes while cutting out-of-sample decay.'+'\n'
+r'  \item \hl{Secondary:} keep every candidate via repair-not-reject; stay cheap (local 3B/2B, \$0) and tradable (costs + cap priced in).'+'\n'
+r'  \item \hl{Validate:} NSE Nifty 50 2002--2025, transfer to S\&P 500 + SSE with one fixed setup.'+'\n'
+r'\end{itemize}'+'\n'+r'\end{block}'+'\n'+r'\begin{block}{1 Problem in 30 seconds}')
assert old in t, 'anchor missing'
t=t.replace(old,new)
io.open(p,'w',encoding='utf-8',newline='').write(t)
print('objectives ok')
