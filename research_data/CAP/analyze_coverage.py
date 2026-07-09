"""Analyze theoretical maximum coverage for each ratio."""
import csv

CSV_PATH = r"C:\Users\EV-Car\CAP\output\nifty_banknifty_ratios.csv"

# Approximate listing/IPO years (when company data starts being available)
LISTING_YEARS = {
    "AUBANK": 2017, "AXISBANK": 2005, "BANDHANBNK": 2018, "BANKBARODA": 2005,
    "CANBK": 2005, "FEDERALBNK": 2005, "HDFCBANK": 2005, "ICICIBANK": 2005,
    "IDFCFIRSTB": 2015, "INDUSINDBK": 2005, "KOTAKBANK": 2005, "PNB": 2005,
    "RBLBANK": 2016, "SBIN": 2005,
    "RELIANCE": 2005, "TCS": 2005, "INFY": 2005, "HCLTECH": 2005,
    "WIPRO": 2005, "TECHM": 2005, "LT": 2005, "ITC": 2005,
    "HINDUNILVR": 2005, "NESTLEIND": 2005, "BHARTIARTL": 2005,
    "SUNPHARMA": 2005, "DRREDDY": 2005, "CIPLA": 2005, "APOLLOHOSP": 2005,
    "MARUTI": 2005, "TATAMOTORS": 2005, "M&M": 2005, "BAJAJ-AUTO": 2005,
    "EICHERMOT": 2005, "HEROMOTOCO": 2005, "TITAN": 2005, "ASIANPAINT": 2005,
    "ULTRACEMCO": 2005, "SHREECEM": 2005, "GRASIM": 2005,
    "ADANIENT": 2005, "ADANIPORTS": 2008, "POWERGRID": 2007, "NTPC": 2005,
    "TATAPOWER": 2005, "COALINDIA": 2010, "ONGC": 2005, "BPCL": 2005,
    "JSWSTEEL": 2005, "TATASTEEL": 2005, "HINDALCO": 2005,
    "BAJFINANCE": 2005, "BAJAJFINSV": 2008, "HDFCLIFE": 2017, "SBILIFE": 2017,
    "BRITANNIA": 2005, "TRENT": 2005, "ETERNAL": 2019,
}

BANKS = {"AUBANK","AXISBANK","BANDHANBNK","BANKBARODA","CANBK",
         "FEDERALBNK","HDFCBANK","ICICIBANK","IDFCFIRSTB",
         "INDUSINDBK","KOTAKBANK","PNB","RBLBANK","SBIN"}

# Insurance / NBFC (no standard Current Ratio)
NBFC_INSURANCE = {"BAJFINANCE","BAJAJFINSV","HDFCLIFE","SBILIFE"}

YEAR_RANGE = range(2005, 2026)
TOTAL_ROWS = 1218  # 58 * 21

# Calculate valid rows per company
total_valid = 0
valid_nonbank = 0
valid_nonfinancial = 0

for ticker, start_yr in LISTING_YEARS.items():
    valid_years = sum(1 for yr in YEAR_RANGE if yr >= start_yr)
    total_valid += valid_years
    if ticker not in BANKS:
        valid_nonbank += valid_years
    if ticker not in BANKS and ticker not in NBFC_INSURANCE:
        valid_nonfinancial += valid_years

print("=" * 65)
print("THEORETICAL MAXIMUM COVERAGE ANALYSIS")
print("=" * 65)
print(f"\nTotal rows in CSV:             {TOTAL_ROWS}")
print(f"Valid rows (company existed):   {total_valid} ({total_valid/TOTAL_ROWS*100:.1f}%)")
print(f"Valid non-bank rows:            {valid_nonbank} ({valid_nonbank/TOTAL_ROWS*100:.1f}%)")
print(f"Valid non-financial rows:       {valid_nonfinancial} ({valid_nonfinancial/TOTAL_ROWS*100:.1f}%)")

print(f"\n{'Ratio':<16} {'Theoretical Max':>15} {'Actual':>10} {'Gap':>10} {'% of Max':>10}")
print("-" * 65)

# Load actual coverage
with open(CSV_PATH, "r", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

ratios = {
    "PE": ("All listed companies (may miss years with negative earnings)", total_valid),
    "ROE": ("All companies", total_valid),
    "ROCE": ("Non-bank only (14 banks excluded)", valid_nonbank),
    "Current_Ratio": ("Non-financial companies ideally, but MC provides for most", total_valid),
    "Debt_Equity": ("All companies (different interpretation for banks)", total_valid),
}

for col, (note, theoretical) in ratios.items():
    actual = sum(1 for r in rows if r.get(col, "").strip())
    gap = theoretical - actual
    pct_of_max = actual / theoretical * 100 if theoretical else 0
    print(f"  {col:<14} {theoretical:>6}/{TOTAL_ROWS} ({theoretical/TOTAL_ROWS*100:4.1f}%)  "
          f"{actual:>5}  {gap:>+6}  {pct_of_max:>8.1f}%")

print(f"\n{'='*65}")
print("BREAKDOWN OF GAPS")
print(f"{'='*65}")

for col, (note, theoretical) in ratios.items():
    print(f"\n  {col} — {note}")
    # Count missing by era
    missing_pre2015 = 0
    missing_2015_plus = 0
    missing_companies = {}
    for r in rows:
        yr = int(r["Year"])
        ticker = r["Company"]
        start = LISTING_YEARS.get(ticker, 2005)
        if yr < start:
            continue  # Company didn't exist
        if col == "ROCE" and ticker in BANKS:
            continue  # N/A for banks
        val = r.get(col, "").strip()
        if not val:
            if yr < 2015:
                missing_pre2015 += 1
            else:
                missing_2015_plus += 1
            missing_companies[ticker] = missing_companies.get(ticker, 0) + 1
    
    print(f"    Missing pre-2015: {missing_pre2015}")
    print(f"    Missing 2015+:    {missing_2015_plus}")
    if missing_companies:
        worst = sorted(missing_companies.items(), key=lambda x: -x[1])[:5]
        print(f"    Most gaps:        {', '.join(f'{t}({n})' for t,n in worst)}")
