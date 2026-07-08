import csv
with open(r"C:\Users\EV-Car\CAP\output\nifty_banknifty_ratios.csv") as f:
    rows = list(csv.DictReader(f))
print(f"Total rows: {len(rows)}")
print(f"Unique companies: {len(set(r['Company'] for r in rows))}")
print(f"Year range: {min(r['Year'] for r in rows)}-{max(r['Year'] for r in rows)}")
print()
print("--- Coverage ---")
for col in ["PE","ROE","ROCE","Current_Ratio","Debt_Equity"]:
    filled = sum(1 for r in rows if r[col])
    print(f"  {col:15s}: {filled:4d}/{len(rows)} ({filled/len(rows)*100:5.1f}%)")
print()
print("--- Sample (RELIANCE 2020-2025) ---")
for r in rows:
    if r["Company"]=="RELIANCE" and r["Year"] in ["2020","2021","2022","2023","2024","2025"]:
        print(f"  {r['Year']} | PE={str(r['PE']):>7s} | ROE={str(r['ROE']):>7s} | ROCE={str(r['ROCE']):>5s} | D/E={str(r['Debt_Equity']):>5s}")
print()
print("--- Sample (HDFCBANK 2020-2025) ---")
for r in rows:
    if r["Company"]=="HDFCBANK" and r["Year"] in ["2020","2021","2022","2023","2024","2025"]:
        print(f"  {r['Year']} | PE={str(r['PE']):>7s} | ROE={str(r['ROE']):>7s} | ROCE={str(r['ROCE']):>5s} | D/E={str(r['Debt_Equity']):>5s}")
