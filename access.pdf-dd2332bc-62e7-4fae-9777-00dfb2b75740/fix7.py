import pathlib
p = pathlib.Path("poster2.tex")
t = p.read_text(encoding="utf-8")
t = t.replace("\\begin{block}{4 Decay: S\\&P halved, SSE quartered (Sharpe change)}",
              "\\begin{block}{4 Decay halved + quartered (Sharpe)}", 1)
t = t.replace("{\\small\\itshape\\color{black!62} S\\&P decay -35.03\\% to -6.77\\%; China -92.08\\% to -46.68\\%. Repair removes overfit noise instead of deleting trees.\\par}",
              "{\\raggedright\\small\\itshape\\color{black!62} S\\&P decay -35.03\\% to -6.77\\%; China -92.08\\% to -46.68\\%. Repair removes overfit noise instead of deleting trees.\\par}", 1)
p.write_text(t, encoding="utf-8")
print("patched7", len(t))
