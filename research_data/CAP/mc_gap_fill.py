"""
Incremental MC scraper — fills ALL gaps (PE, ROE, ROCE, CR, D/E).
Saves after each company. Only fetches for missing data.
Uses direct MC financial URL pattern with known slugs.
"""
import csv, re, sys, time, json
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

CSV_PATH = Path(__file__).resolve().parent / "output" / "nifty_banknifty_ratios.csv"
YEAR_RANGE = range(2005, 2026)
FIELDS = ["PE", "ROE", "ROCE", "Current_Ratio", "Debt_Equity"]
BANK_TICKERS = {"AUBANK","AXISBANK","BANDHANBNK","BANKBARODA","CANBK",
                "FEDERALBNK","HDFCBANK","ICICIBANK","IDFCFIRSTB",
                "INDUSINDBK","KOTAKBANK","PNB","RBLBANK","SBIN"}

# Complete MC slug map (slug, code) — verified 2026-05-08
MC_FULL = {
    "RELIANCE": ("relianceindustries", "RI"),
    "TCS": ("tataconsultancyservices", "TCS"),
    "INFY": ("infosys", "IT"),
    "HCLTECH": ("hcltechnologies", "HCL02"),
    "WIPRO": ("wipro", "W05"),
    "TECHM": ("techmahindra", "TM4"),
    "LT": ("larsentoubro", "LT"),
    "ITC": ("itc", "ITC"),
    "HINDUNILVR": ("hindustanunilever", "HU"),
    "NESTLEIND": ("nestleindia", "NI15"),
    "BHARTIARTL": ("bhartiairtel", "BA08"),
    "SUNPHARMA": ("sunpharmaceuticalindustries", "SPI"),
    "DRREDDY": ("drreddyslaboratories", "DRL"),
    "CIPLA": ("cipla", "C"),
    "APOLLOHOSP": ("apollohospitalsenterprises", "AH"),
    "MARUTI": ("marutisuzukiindia", "MS24"),
    "TATAMOTORS": ("tatamotors", "TM03"),
    "M&M": ("mahindramahindra", "MM"),
    "BAJAJ-AUTO": ("bajaj-auto", "BA10"),
    "EICHERMOT": ("eichermotors", "EM"),
    "HEROMOTOCO": ("heromotocorp", "HHM"),
    "TITAN": ("titancompany", "TI01"),
    "ASIANPAINT": ("asianpaints", "AP"),
    "ULTRACEMCO": ("ultratechcement", "UTC01"),
    "SHREECEM": ("shreecements", "SC20"),
    "GRASIM": ("grasimindustries", "GI01"),
    "ADANIENT": ("adanienterprisesltd", "AE13"),
    "ADANIPORTS": ("adaniportsspecialeconomiczone", "MPS"),
    "POWERGRID": ("powergridcorporationofindia", "PGC"),
    "NTPC": ("ntpc", "NTP"),
    "TATAPOWER": ("tatapowercompany", "TPC"),
    "COALINDIA": ("coalindia", "CI11"),
    "ONGC": ("oilnaturalgascorporation", "ONG"),
    "BPCL": ("bharatpetroleumcorporation", "BPC"),
    "JSWSTEEL": ("jswsteel", "JSW01"),
    "TATASTEEL": ("tatasteel", "TIS"),
    "HINDALCO": ("hindalcoindustries", "HI"),
    "BAJFINANCE": ("bajajfinance", "BAF"),
    "BAJAJFINSV": ("bajajfinserv", "BF04"),
    # HDFCLIFE: MC has no ratios data for this company
    "SBILIFE": ("sbilifeinsurancecompanylimited", "SLI03"),
    "BRITANNIA": ("britanniaindustries", "BI"),
    "TRENT": ("trent", "T03"),
    "ETERNAL": ("zomatolimited", "Z"),
    # Banks
    "AXISBANK": ("axisbank", "AB16"),
    "HDFCBANK": ("hdfcbank", "HDF01"),
    "ICICIBANK": ("icicibank", "ICI02"),
    "KOTAKBANK": ("kotakmahindrabank", "KMB"),
    "SBIN": ("statebankofindia", "SBI"),
    "INDUSINDBK": ("indusindbank", "IIB"),
    "BANKBARODA": ("bankofbaroda", "BOB"),
    "PNB": ("punjabnationalbank", "PNB05"),
    "CANBK": ("canarabank", "CB06"),
    "FEDERALBNK": ("federalbank", "FB"),
    "AUBANK": ("ausmallfinancebank", "ASF02"),
    "BANDHANBNK": ("bandhanbank", "BB09"),
    # IDFCFIRSTB: MC has no ratios data for this company
    "RBLBANK": ("rblbank", "RB03"),
}

# ─── Load existing CSV ───
def load_csv():
    data = {}
    if CSV_PATH.exists():
        with open(CSV_PATH, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                key = (row["Company"], int(row["Year"]))
                data[key] = row
    return data

def save_csv(data):
    fields = ["Year", "Company", "Sector", "PE", "ROE", "ROCE", "Current_Ratio", "Debt_Equity"]
    rows = sorted(data.values(), key=lambda r: (r["Company"], int(r["Year"])))
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

def get_missing(data, ticker, fields_to_check):
    """Return set of fields that have ANY missing year for this ticker."""
    missing = set()
    for field in fields_to_check:
        for yr in YEAR_RANGE:
            key = (ticker, yr)
            if key in data:
                val = data[key].get(field, "")
                if not val or not val.strip():
                    missing.add(field)
                    break
            else:
                missing.add(field)
                break
    return missing

# ─── Parse MC ratios page ───
def _extract_years(texts):
    years = []
    for t in texts:
        m = re.search(r"(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[\s'\\-]*([0-9]{2,4})", t, re.I)
        if m:
            yr = int(m.group(1))
            years.append(yr + 2000 if yr < 100 else yr)
    return years


def _to_float(val):
    v = val.strip().replace(",", "")
    if not v or v == "--":
        return None
    v = re.sub(r"[^0-9.\\-]", "", v)
    if not v or v in {"-", ".", "-."}:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def find_mc_table(page, keywords):
    table = page.query_selector("table.mctable1")
    if table:
        return table
    tables = page.query_selector_all("table")
    for t in tables:
        try:
            text = t.inner_text().lower()
            if any(k in text for k in keywords):
                return t
        except:
            pass
    return None


def parse_mc_table(page):
    """Extract ALL ratios from MC mctable1, including PE derived from Earnings Yield."""
    table = find_mc_table(page, ["indicators", "return on networth", "return on equity", "earnings yield", "current ratio"])
    if not table:
        return {}, []
    rows = table.query_selector_all("tr")
    years = []
    result = {}
    
    for row in rows:
        cells = row.query_selector_all("td, th")
        texts = [c.inner_text().strip() for c in cells]
        if not texts:
            continue
        label = texts[0]
        
        if not years:
            maybe_years = _extract_years(texts[1:])
            if len(maybe_years) >= 3:
                years = maybe_years
                continue
        
        if not years:
            continue
        
        ll = label.lower()
        field = None
        if "current ratio" in ll:
            field = "Current_Ratio"
        elif "return on networth" in ll or "return on equity" in ll:
            field = "ROE"
        elif "return on capital employed" in ll:
            field = "ROCE"
        elif "total debt/equity" in ll or "debt equity" in ll:
            field = "Debt_Equity"
        elif "earnings yield" in ll:
            # Derive PE = 1 / Earnings_Yield
            for i, yr in enumerate(years):
                idx = i + 1
                if idx < len(texts):
                    ey = _to_float(texts[idx])
                    if ey is not None and ey > 0 and yr in YEAR_RANGE:
                        pe = round(1.0 / ey, 2)
                        result[("PE", yr)] = pe
            continue
        
        if field:
            for i, yr in enumerate(years):
                idx = i + 1
                if idx < len(texts):
                    val = _to_float(texts[idx])
                    if val is not None and yr in YEAR_RANGE:
                        result[(field, yr)] = val
    
    return result, years


# ─── Parse MC balance sheet / P&L tables ───
def _norm_label(label: str) -> str:
    return re.sub(r"[^a-z0-9]", "", label.lower())


def _find_series(data: dict[str, dict[int, float]], keywords: list[str]) -> dict[int, float]:
    for label, series in data.items():
        n = _norm_label(label)
        if any(k in n for k in keywords):
            return series
    return {}


def parse_mc_statement_table(page):
    table = find_mc_table(page, ["equity capital", "total debt", "total borrowings", "total share capital", "shareholders funds", "net profit", "operating profit", "ebit", "profit before interest"])
    if not table:
        return {}, []
    rows = table.query_selector_all("tr")
    years = []
    data: dict[str, dict[int, float]] = {}

    for row in rows:
        cells = row.query_selector_all("td, th")
        texts = [c.inner_text().strip() for c in cells]
        if not texts:
            continue
        label = texts[0]

        if not years:
            maybe_years = _extract_years(texts[1:])
            if len(maybe_years) >= 3:
                years = maybe_years
                continue

        if not years:
            continue

        series: dict[int, float] = {}
        for i, yr in enumerate(years):
            idx = i + 1
            if idx < len(texts):
                val = _to_float(texts[idx])
                if val is not None and yr in YEAR_RANGE:
                    series[yr] = val
        if series:
            data[label] = series

    return data, years


def fetch_statement_pages(page, slug, code, section, anchor):
    data: dict[str, dict[int, float]] = {}
    for pg in range(1, 6):
        if pg == 1:
            url = f"https://www.moneycontrol.com/financials/{slug}/{section}/{code}{anchor}"
        else:
            url = f"https://www.moneycontrol.com/financials/{slug}/{section}/{code}/{pg}{anchor}"
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        time.sleep(3)
        if "Access Denied" in page.title():
            return {}, True
        page_data, _ = parse_mc_statement_table(page)
        if not page_data:
            break
        for label, series in page_data.items():
            if label not in data:
                data[label] = {}
            data[label].update(series)
        time.sleep(2)
    return data, False


def derive_ratios_from_statements(bs_data, pl_data, ticker):
    results: dict[tuple[str, int], float] = {}
    is_bank = ticker in BANK_TICKERS

    current_assets = _find_series(bs_data, ["totalcurrentassets", "currentassets"])
    current_liab = _find_series(bs_data, ["totalcurrentliabilities", "currentliabilities"])
    total_assets = _find_series(bs_data, ["totalassets"])
    capital_employed = _find_series(bs_data, ["capitalemployed"])
    total_debt = _find_series(bs_data, ["totaldebt", "totalborrowings", "borrowings"])
    equity = _find_series(bs_data, ["totalshareholdersfunds", "shareholdersfunds", "totalequity", "shareholderfunds"])

    net_profit = _find_series(pl_data, ["netprofit", "profitaftertax", "netprofitloss"])
    ebit = _find_series(pl_data, ["ebit", "profitbeforeinterestandtax", "operatingprofit"])

    for yr in YEAR_RANGE:
        eq = equity.get(yr)
        if eq is not None and eq != 0:
            np = net_profit.get(yr)
            if np is not None:
                results[("ROE", yr)] = round((np / eq) * 100, 2)
            td = total_debt.get(yr)
            if td is not None:
                results[("Debt_Equity", yr)] = round(td / eq, 2)

        if not is_bank:
            ca = current_assets.get(yr)
            cl = current_liab.get(yr)
            if ca is not None and cl is not None and cl != 0:
                results[("Current_Ratio", yr)] = round(ca / cl, 2)

            ce = capital_employed.get(yr)
            if ce is None:
                ta = total_assets.get(yr)
                if ta is not None and cl is not None:
                    ce = ta - cl
            if ce is not None and ce != 0:
                op = ebit.get(yr)
                if op is not None:
                    results[("ROCE", yr)] = round((op / ce) * 100, 2)

    return results

# ─── Main ───
def main():
    data = load_csv()
    print(f"Loaded {len(data)} existing rows")
    
    # Determine which companies need MC data
    non_bank_fields = ["PE", "ROE", "ROCE", "Current_Ratio", "Debt_Equity"]
    bank_fields = ["PE", "ROE", "Current_Ratio", "Debt_Equity"]  # No ROCE for banks
    
    companies_to_scrape = []
    for ticker in MC_FULL:
        fields = bank_fields if ticker in BANK_TICKERS else non_bank_fields
        missing = get_missing(data, ticker, fields)
        if missing:
            companies_to_scrape.append((ticker, missing))
    
    print(f"Companies needing MC data: {len(companies_to_scrape)}")
    if not companies_to_scrape:
        print("Nothing to do!")
        return
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1366, "height": 768},
        )
        page = ctx.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
        
        for ticker, missing_fields in companies_to_scrape:
            slug, code = MC_FULL[ticker]
            print(f"\n  {ticker} (need: {','.join(sorted(missing_fields))}): ", end="")
            
            all_mc_data = {}
            blocked = False
            
            # Paginate through MC pages
            for pg in range(1, 6):  # 5 pages = ~25 years
                if pg == 1:
                    url = f"https://www.moneycontrol.com/financials/{slug}/ratiosVI/{code}#RI"
                else:
                    url = f"https://www.moneycontrol.com/financials/{slug}/ratiosVI/{code}/{pg}#RI"
                
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=20000)
                    time.sleep(4)
                    
                    if "Access Denied" in page.title():
                        print("BLOCKED!", end=" ")
                        blocked = True
                        break
                    
                    page_data, page_years = parse_mc_table(page)
                    if not page_data:
                        break
                    
                    all_mc_data.update(page_data)
                    
                except Exception as e:
                    print(f"pg{pg} err: {str(e)[:40]}", end=" ")
                    break
                
                time.sleep(2)
            
            if blocked:
                time.sleep(5)
                continue

            # Statement-based fallback for missing ratios
            statement_fields = {"ROE", "ROCE", "Current_Ratio", "Debt_Equity"}
            if missing_fields & statement_fields:
                try:
                    bs_data, bs_blocked = fetch_statement_pages(page, slug, code, "balance-sheetVI", "#BS")
                    if bs_blocked:
                        print("BS_BLOCKED", end=" ")
                        bs_data = {}
                    pl_data, pl_blocked = fetch_statement_pages(page, slug, code, "profit-lossVI", "#PL")
                    if pl_blocked:
                        print("PL_BLOCKED", end=" ")
                        pl_data = {}
                    if bs_data or pl_data:
                        derived = derive_ratios_from_statements(bs_data, pl_data, ticker)
                        all_mc_data.update(derived)
                except Exception as e:
                    print(f"stmt err: {str(e)[:30]}", end=" ")
            
            # Store the data
            filled = 0
            for (field, yr), val in all_mc_data.items():
                if field not in missing_fields:
                    continue
                key = (ticker, yr)
                if key in data:
                    existing = data[key].get(field, "")
                    if not existing or not existing.strip():
                        data[key][field] = str(val)
                        filled += 1
            
            print(f"{filled} new values ({len(all_mc_data)} total from MC)")
            
            # Save after each company
            save_csv(data)
            time.sleep(2)
        
        browser.close()
    
    # Final coverage
    print(f"\n{'='*60}")
    print("FINAL COVERAGE")
    print(f"{'='*60}")
    total = len(data)
    for col in FIELDS:
        filled = sum(1 for r in data.values() if r.get(col, "").strip())
        print(f"  {col:15s}: {filled:4d}/{total} ({filled/total*100:5.1f}%)")

if __name__ == "__main__":
    main()
