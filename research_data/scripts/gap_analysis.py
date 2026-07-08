"""Per-company gap analysis + identify broken MC slugs."""
import csv

rows = list(csv.DictReader(open(r"C:\Users\EV-Car\CAP\output\nifty_banknifty_ratios.csv")))
fields = ["PE","ROE","ROCE","Current_Ratio","Debt_Equity"]

companies = {}
for r in rows:
    t = r["Company"]
    if t not in companies:
        companies[t] = {f: 0 for f in fields}
        companies[t]["total"] = 0
    companies[t]["total"] += 1
    for f in fields:
        if r.get(f, "").strip():
            companies[t][f] += 1

print(f"{'Ticker':<14} {'PE':>4} {'ROE':>4} {'ROCE':>5} {'CR':>4} {'D/E':>4}  /Yrs")
print("-" * 50)
for t in sorted(companies):
    c = companies[t]
    has_gap = any(c[f] < c["total"] for f in fields)
    if has_gap:
        flags = []
        for f in fields:
            if c[f] == 0:
                flags.append(f"NO_{f}")
            elif c[f] < c["total"] - 5:
                flags.append(f"LOW_{f}")
        flag_str = " " + ",".join(flags) if flags else ""
        print(f"  {t:<12} {c['PE']:>4} {c['ROE']:>4} {c['ROCE']:>5} {c['Current_Ratio']:>4} {c['Debt_Equity']:>4}  /{c['total']:>3}{flag_str}")

print(f"\n{'='*50}")
print("COMPANIES WITH FULL COVERAGE (all 21 years filled):")
full = [t for t in sorted(companies) if all(companies[t][f] == companies[t]["total"] for f in fields)]
print(f"  {len(full)} companies: {', '.join(full)}")
