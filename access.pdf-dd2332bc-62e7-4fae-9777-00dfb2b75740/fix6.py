import pathlib
p = pathlib.Path("poster2.tex")
t = p.read_text(encoding="utf-8")
old = t[t.index("\\begin{block}{4 Decay:"): t.index("instead of deleting trees.}\n\\end{block}")+len("instead of deleting trees.}\n\\end{block}")]
new = """\\begin{block}{4 Decay: S\\&P halved, SSE quartered (Sharpe change)}
\\begin{minipage}{\\linewidth}\\centering
{\\footnotesize
\\setlength{\\tabcolsep}{0.12cm}\\renewcommand{\\arraystretch}{1.25}
\\begin{tabular}{@{}lcc@{}}
\\toprule
\\textbf{Market / engine} & \\textbf{OOS Sharpe} & \\textbf{Decay} \\\\
\\midrule
S\\&P Vanilla GP & 0.905 & \\textcolor{bad}{\\bfseries -35.03\\%} \\\\
S\\&P HMM-GP & 0.974 & -20.71\\% \\\\
S\\&P \\textbf{LLM-GP (ours)} & \\textbf{1.075} & \\textcolor{good}{\\bfseries -6.77\\%} \\\\
\\midrule
SSE Vanilla GP & 0.035 & \\textcolor{bad}{\\bfseries -92.08\\%} \\\\
SSE HMM-GP & 0.232 & -63.28\\% \\\\
SSE \\textbf{LLM-GP (ours)} & \\textbf{0.067} & \\textcolor{good}{\\bfseries -46.68\\%} \\\\
\\bottomrule
\\end{tabular}\\par}
\\vspace{0.2cm}
{\\small\\itshape\\color{black!62} S\\&P decay -35.03\\% to -6.77\\%; China -92.08\\% to -46.68\\%. Repair removes overfit noise instead of deleting trees.\\par}
\\end{minipage}
\\end{block}"""
assert old.startswith("\\begin{block}{4"), "anchor miss"
t = t.replace(old, new)
p.write_text(t, encoding="utf-8")
print("patched6", len(t))
