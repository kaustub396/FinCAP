"""Targeted PE fetch for 35 companies missing PE data using INDIANAPI_API_KEY_2."""
import csv, re, sys, time
import requests
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ENV_PATH = Path(__file__).resolve().parent / "env" / ".env"
CSV_PATH = Path(__file__).resolve().parent / "output" / "nifty_banknifty_ratios.csv"
YEAR_RANGE = range(2005, 2026)

# Load new API key
env = {}
for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")

api_key = env.get("INDIANAPI_API_KEY_2", "")
if not api_key:
    print("ERROR: INDIANAPI_API_KEY_2 not found in .env")
    sys.exit(1)
print(f"Using INDIANAPI_API_KEY_2")

# Load existing CSV
rows_by_key = {}
with open(CSV_PATH, "r", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        rows_by_key[(row["Company"], int(row["Year"]))] = row

# Companies missing PE
MISSING_PE = [
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "BAJAJ-AUTO",
    "BAJAJFINSV", "BAJFINANCE", "BHARTIARTL", "BPCL", "BRITANNIA",
    "CIPLA", "COALINDIA", "DRREDDY", "EICHERMOT", "ETERNAL",
    "GRASIM", "HDFCLIFE", "HEROMOTOCO", "HINDALCO", "JSWSTEEL",
    "M&M", "MARUTI", "NESTLEIND", "NTPC", "ONGC",
    "POWERGRID", "SBILIFE", "SHREECEM", "SUNPHARMA", "TATAMOTORS",
    "TATAPOWER", "TATASTEEL", "TITAN", "TRENT", "ULTRACEMCO",
]

base = "https://stock.indianapi.in"
hdrs = {"x-api-key": api_key}
total_filled = 0

for ticker in MISSING_PE:
    print(f"  {ticker}: ", end="")
    try:
        for attempt in range(3):
            r = requests.get(f"{base}/historical_data",
                             params={"stock_name": ticker, "period": "max", "filter": "pe"},
                             headers=hdrs, timeout=30)
            if r.status_code == 429:
                wait = 5 * (attempt + 1)
                print(f"429, wait {wait}s...", end="")
                time.sleep(wait)
                continue
            break
        
        if r.status_code == 200:
            datasets = r.json().get("datasets", [])
            pe_ds = next((d for d in datasets if d.get("metric") == "Price to Earning"), None)
            if pe_ds:
                yearly_pe = {}
                for pt in pe_ds.get("values", []):
                    date_str, val = pt[0], pt[1]
                    yr = int(date_str[:4])
                    if isinstance(val, str):
                        try: val = float(val)
                        except: continue
                    if val and yr in YEAR_RANGE:
                        yearly_pe.setdefault(yr, []).append(val)
                
                count = 0
                for yr, vals in yearly_pe.items():
                    vals.sort()
                    median = vals[len(vals) // 2]
                    key = (ticker, yr)
                    if key in rows_by_key:
                        rows_by_key[key]["PE"] = str(round(median, 2))
                        count += 1
                total_filled += count
                print(f"{count} years of PE")
            else:
                print("no PE dataset")
        else:
            print(f"HTTP {r.status_code}")
    except Exception as e:
        print(f"error: {e}")
    
    time.sleep(1.5)

# Save updated CSV
fields = ["Year", "Company", "Sector", "PE", "ROE", "ROCE", "Current_Ratio", "Debt_Equity"]
all_rows = sorted(rows_by_key.values(), key=lambda r: (r["Company"], int(r["Year"])))
with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(all_rows)

print(f"\nDone! Filled {total_filled} PE values for {len(MISSING_PE)} companies")

# Final coverage
total = len(all_rows)
for col in ["PE", "ROE", "ROCE", "Current_Ratio", "Debt_Equity"]:
    filled = sum(1 for r in all_rows if r.get(col) and r[col].strip())
    print(f"  {col:15s}: {filled:4d}/{total} ({filled/total*100:5.1f}%)")
