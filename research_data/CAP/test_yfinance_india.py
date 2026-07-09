"""Test yfinance for Indian stock fundamental data coverage."""
import yfinance as yf
import json

ticker = yf.Ticker("RELIANCE.NS")

# 1) Check .info for PE, current ratios etc.
info = ticker.info
print("=== .info (selected fields) ===")
for k in ["trailingPE", "forwardPE", "returnOnEquity", "debtToEquity",
           "currentRatio", "sector", "industry", "longName"]:
    print(f"  {k}: {info.get(k)}")
print()

# 2) Balance sheet — how many years?
bs = ticker.balance_sheet
print("=== Balance Sheet ===")
print(f"  Shape: {bs.shape}")
print(f"  Columns (dates): {list(bs.columns)}")
print(f"  Row labels: {list(bs.index)[:15]}")
# Check for keys we need to derive ratios
for key in ["Total Current Assets", "Total Current Liabilities",
            "Current Assets", "Current Liabilities",
            "Total Debt", "Stockholders Equity",
            "Ordinary Shares Number"]:
    val = bs.loc[key].to_dict() if key in bs.index else "NOT FOUND"
    if isinstance(val, dict):
        print(f"  {key}: {len(val)} years")
    else:
        print(f"  {key}: {val}")
print()

# 3) Financials (income statement)
fs = ticker.financials
print("=== Income Statement ===")
print(f"  Shape: {fs.shape}")
print(f"  Columns (dates): {list(fs.columns)}")
print(f"  Row labels: {list(fs.index)[:15]}")
print()

# 4) Check quarterly balance sheet for more depth
qbs = ticker.quarterly_balance_sheet
print("=== Quarterly Balance Sheet ===")
print(f"  Shape: {qbs.shape}")
print(f"  Columns (dates): {list(qbs.columns)}")
print()

# 5) Try getting key stats
print("=== Key Stats for derivation ===")
try:
    # Check if we can get PE, ROE, ROCE, Current Ratio, Debt/Equity
    print(f"  trailingPE: {info.get('trailingPE')}")
    print(f"  returnOnEquity (ROE): {info.get('returnOnEquity')}")
    print(f"  returnOnAssets: {info.get('returnOnAssets')}")
    print(f"  currentRatio: {info.get('currentRatio')}")
    print(f"  debtToEquity: {info.get('debtToEquity')}")
    print(f"  sector: {info.get('sector')}")
except Exception as e:
    print(f"  Error: {e}")
