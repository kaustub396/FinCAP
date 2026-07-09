"""Deep test: can yfinance give us more than 5 years of historical data?"""
import yfinance as yf

ticker = yf.Ticker("RELIANCE.NS")

# Check if there are hidden methods for historical fundamentals
print("=== All available data attributes ===")
attrs = [a for a in dir(ticker) if not a.startswith('_')]
print(attrs)
print()

# Try get_balance_sheet with older dates
print("=== Annual Balance Sheet dates ===")
bs = ticker.balance_sheet
print("Dates:", [str(c.date()) for c in bs.columns])
print()

# Try to see if we can get older statements via .get_balance_sheet
try:
    bs2 = ticker.get_balance_sheet(freq='yearly')
    print("get_balance_sheet dates:", [str(c.date()) for c in bs2.columns])
except Exception as e:
    print(f"get_balance_sheet error: {e}")

# Check if .info has historical PE data
info = ticker.info
hist_pe_keys = [k for k in info.keys() if 'pe' in k.lower() or 'PE' in k or 'earning' in k.lower()]
print("\nPE-related keys in .info:", hist_pe_keys)
print({k: info[k] for k in hist_pe_keys if info[k] is not None})

# Check .key_stats or similar
try:
    print("\n=== ticker.earnings ===")
    print(ticker.earnings)
except Exception as e:
    print(f"earnings error: {e}")

print("\n=== Conclusion ===")
print(f"Balance sheet covers: {bs.shape[1]} years")
print(f"yfinance provides CURRENT ratios via .info but NOT historical annual ratios")
print(f"For 2005-2025 historical ratios, yfinance is INSUFFICIENT")
