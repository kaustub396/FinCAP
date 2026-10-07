import pathlib
p = pathlib.Path("poster2.tex")
t = p.read_text(encoding="utf-8")

old_b3 = t[t.index("\\begin{block}{3 Does it work?"): t.index("\\end{block}", t.index("beats the quant ceiling"))+len("\\end{block}")]
new_b3 = """\\begin{block}{3 System architecture (paper Fig.~1, middle)}
\\centering
\\includegraphics[width=\\linewidth,keepaspectratio]{images/38de923ab8b5dcfc8845af49392f1122074f030c0adba45a84530c30bf42c1bf.jpg}
\\figcap{Figure 1. Dual two-stage framework: (1) regime-aware factor engine (AFM macro + HMM states + regime GP) and (2) post-evolution Two-Stage LLM Refiner (Llama-3B judge, Gemma-2B closed-vocab repair) with AST + validation guards.}
\\end{block}"""
assert old_b3.startswith("\\begin{block}{3"), "b3 anchor miss"
t = t.replace(old_b3, new_b3)

old_b4 = t[t.index("\\begin{block}{4 Decay:"): t.index("\\end{block}", t.index("instead of deleting trees"))+len("\\end{block}")]
new_b4 = """\\begin{block}{4 Decay: S\\&P halved, SSE quartered (Sharpe change)}
{\\small
\\setlength{\\tabcolsep}{0.18cm}\\renewcommand{\\arraystretch}{1.25}
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
\\end{tabular}}
\\figcap{S\\&P decay -35.03\\% to -6.77\\%; China -92.08\\% to -46.68\\%. Repair removes overfit noise instead of deleting trees.}
\\end{block}"""
assert old_b4.startswith("\\begin{block}{4"), "b4 anchor miss"
t = t.replace(old_b4, new_b4)

p.write_text(t, encoding="utf-8")
print("patched4", len(t))
