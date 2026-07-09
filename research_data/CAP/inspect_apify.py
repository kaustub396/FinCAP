"""Inspect the Apify dataset structure."""
import re, requests, json
from pathlib import Path

text = Path(r"C:\Users\EV-Car\CAP\env\.env").read_text(encoding="utf-8")
url = re.search(r"^APIFY_GET_DATASETITEMS_API_KEY\s*=\s*(.+)$", text, re.M).group(1).strip().strip('"').strip("'")

resp = requests.get(url, timeout=90)
data = resp.json()

print("Total items:", len(data))
print()

# Show all company names
for i, item in enumerate(data):
    print(f"  [{i}] {item.get('company_name', 'N/A')}")
print()

first = data[0]
print("Top-level keys:", list(first.keys()))
print()

# Ratios
ratios = first.get("ratios", [])
print("ratios metrics:", [x.get("Metric") for x in ratios if isinstance(x, dict)])
print("ratios sample (first 2):", json.dumps(ratios[:2], indent=2))
print()

# Balance sheet
bs = first.get("balance_sheet", [])
print("balance_sheet metrics:", [x.get("Metric") for x in bs if isinstance(x, dict)])
print()

# Profit and loss
pl = first.get("profit_and_loss", {})
print("profit_and_loss keys:", list(pl.keys()) if isinstance(pl, dict) else type(pl))
if isinstance(pl, dict):
    ad = pl.get("annual_data", [])
    print("P&L annual_data metrics:", [x.get("Metric") for x in ad if isinstance(x, dict)][:30])
    if ad:
        print("P&L annual sample (first):", json.dumps(ad[0], indent=2))
print()

# Cash flow
cf = first.get("cash_flow", [])
print("cash_flow metrics:", [x.get("Metric") for x in cf if isinstance(x, dict)])
print()

# Quarters
q = first.get("quarters", [])
print("quarters metrics:", [x.get("Metric") for x in q if isinstance(x, dict)])
print()

# Check what year columns exist in ratios
if ratios:
    sample = ratios[0]
    print("Year columns in ratios[0]:", [k for k in sample.keys() if k != "Metric"])
