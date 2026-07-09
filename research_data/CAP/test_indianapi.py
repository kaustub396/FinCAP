"""Part 2: Test remaining endpoints for ratio coverage + historical depth."""
import json, re, requests, sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

text = Path(r"C:\Users\EV-Car\CAP\env\.env").read_text(encoding="utf-8")
m = re.search(r"^INDIANAPI_API_KEY\s*=\s*(.+)$", text, re.M)
api_key = m.group(1).strip().strip('"').strip("'")

BASE = "https://stock.indianapi.in"
headers = {"x-api-key": api_key}

def api_get(endpoint, params):
    r = requests.get(f"{BASE}{endpoint}", params=params, headers=headers, timeout=30)
    return r.status_code, r.json() if r.status_code == 200 else r.text

# ---- 1. Check keyMetrics more carefully ----
print("=" * 60)
print("1. keyMetrics with proper labels")
print("=" * 60)
code, data = api_get("/stock", {"name": "RELIANCE"})
km = data.get("keyMetrics", {})
for section, vals in km.items():
    if isinstance(vals, list):
        print(f"\n  [{section}] ({len(vals)} items)")
        for v in vals:
            if isinstance(v, dict):
                title = v.get("title", v.get("name", v.get("label", "?")))
                value = v.get("value", v.get("displayValue", "?"))
                print(f"    {title}: {value}")

# ---- 2. financials - check fiscal years available ----
print()
print("=" * 60)
print("2. Fiscal years in financials")
print("=" * 60)
fins = data.get("financials", [])
print(f"Total entries: {len(fins)}")
for f in fins:
    fy = f.get("FiscalYear", "?")
    typ = f.get("Type", "?")
    end = f.get("EndDate", "?")
    sfm = f.get("stockFinancialMap", {})
    print(f"  FY={fy} | Type={typ} | EndDate={end} | fields={len(sfm)}")

# ---- 3. /historical_data filters ----
print()
print("=" * 60)
print("3. /historical_data all filters")
print("=" * 60)
for filt in ["pe", "default", "price", "sm", "evebitda", "ptb", "mcs"]:
    code, d = api_get("/historical_data", {"stock_name": "RELIANCE", "period": "max", "filter": filt})
    if code == 200 and isinstance(d, dict):
        datasets = d.get("datasets", [])
        for ds in datasets:
            metric = ds.get("metric", "?")
            vals = ds.get("values", [])
            earliest = vals[0][0] if vals else "?"
            latest = vals[-1][0] if vals else "?"
            print(f"  filter='{filt}' | metric='{metric}' | {len(vals)} pts | {earliest} -> {latest}")
    else:
        print(f"  filter='{filt}': HTTP {code}")

# ---- 4. /statement endpoint ----
print()
print("=" * 60)
print("4. /statement endpoint - try various stats")
print("=" * 60)
for stat in ["balance_sheet", "income_statement", "cash_flow", "ratios", 
             "balance-sheet", "income-statement", "cash-flow",
             "quarterly", "annual", "profit_loss"]:
    code, d = api_get("/statement", {"stock_name": "RELIANCE", "stats": stat})
    if code == 200:
        if isinstance(d, dict):
            print(f"  stats='{stat}': dict keys={list(d.keys())[:8]}")
        elif isinstance(d, list):
            print(f"  stats='{stat}': list of {len(d)} items")
    else:
        err = str(d)[:80] if isinstance(d, str) else str(d)[:80]
        print(f"  stats='{stat}': HTTP {code} | {err}")

# ---- 5. /historical_stats endpoint ----
print()
print("=" * 60)
print("5. /historical_stats endpoint")
print("=" * 60)
for stat in ["pe", "roe", "roce", "current_ratio", "debt_equity", "eps", 
             "revenue", "profit", "dividend", "book_value", "net_income",
             "return_on_equity", "price_to_earnings"]:
    code, d = api_get("/historical_stats", {"stock_name": "RELIANCE", "stats": stat})
    if code == 200:
        if isinstance(d, dict):
            keys = list(d.keys())[:5]
            # Check for data arrays
            for k in d:
                if isinstance(d[k], list) and d[k]:
                    print(f"  stats='{stat}': {k}={len(d[k])} items | first={d[k][0]}")
                    break
            else:
                print(f"  stats='{stat}': keys={keys}")
        elif isinstance(d, list):
            print(f"  stats='{stat}': {len(d)} items | first={d[0] if d else 'empty'}")
    else:
        print(f"  stats='{stat}': HTTP {code}")
