"""
CAP Data Pipeline — Nifty50 + BankNifty Financial Ratios (2005-2025)
Sources: IndianAPI.in (PE), Screener.in (ROCE/ROE/D-E), Apify (supplementary), MoneyControl (fallback)
Output:  output/nifty_banknifty_ratios.csv
"""
from __future__ import annotations
import csv, json, os, re, sys, time
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ──────────────────────── CONFIG ────────────────────────
ENV_PATH = Path(__file__).resolve().parent / "env" / ".env"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_CSV = OUTPUT_DIR / "nifty_banknifty_ratios.csv"
YEAR_RANGE = range(2005, 2026)  # 2005..2025 inclusive

HEADERS_BROWSER = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# ──────────────────────── COMPANY REGISTRY ────────────────────────
# (ticker, screener_slug, sector)
# Nifty50 + BankNifty combined, duplicates removed
COMPANIES: list[tuple[str, str, str]] = [
    # --- BANKING (BankNifty) ---
    ("AUBANK", "AUBANK", "Banking"),
    ("AXISBANK", "AXISBANK", "Banking"),
    ("BANDHANBNK", "BANDHANBNK", "Banking"),
    ("BANKBARODA", "BANKBARODA", "Banking"),
    ("CANBK", "CANBK", "Banking"),
    ("FEDERALBNK", "FEDERALBNK", "Banking"),
    ("HDFCBANK", "HDFCBANK", "Banking"),
    ("ICICIBANK", "ICICIBANK", "Banking"),
    ("IDFCFIRSTB", "IDFCFIRSTB", "Banking"),
    ("INDUSINDBK", "INDUSINDBK", "Banking"),
    ("KOTAKBANK", "KOTAKBANK", "Banking"),
    ("PNB", "PNB", "Banking"),
    ("RBLBANK", "RBLBANK", "Banking"),
    ("SBIN", "SBIN", "Banking"),
    # --- NIFTY 50 (non-bank) ---
    ("RELIANCE", "RELIANCE", "Oil & Gas"),
    ("TCS", "TCS", "IT"),
    ("INFY", "INFY", "IT"),
    ("HCLTECH", "HCLTECH", "IT"),
    ("WIPRO", "WIPRO", "IT"),
    ("TECHM", "TECHM", "IT"),
    ("LT", "LT", "Infrastructure"),
    ("ITC", "ITC", "FMCG"),
    ("HINDUNILVR", "HINDUNILVR", "FMCG"),
    ("NESTLEIND", "NESTLEIND", "FMCG"),
    ("BHARTIARTL", "BHARTIARTL", "Telecom"),
    ("SUNPHARMA", "SUNPHARMA", "Pharma"),
    ("DRREDDY", "DRREDDY", "Pharma"),
    ("CIPLA", "CIPLA", "Pharma"),
    ("APOLLOHOSP", "APOLLOHOSP", "Healthcare"),
    ("MARUTI", "MARUTI", "Automobile"),
    ("TATAMOTORS", "TMCV", "Automobile"),
    ("M&M", "M%26M", "Automobile"),
    ("BAJAJ-AUTO", "BAJAJ-AUTO", "Automobile"),
    ("EICHERMOT", "EICHERMOT", "Automobile"),
    ("HEROMOTOCO", "HEROMOTOCO", "Automobile"),
    ("TITAN", "TITAN", "Consumer"),
    ("ASIANPAINT", "ASIANPAINT", "Consumer"),
    ("ULTRACEMCO", "ULTRACEMCO", "Cement"),
    ("SHREECEM", "SHREECEM", "Cement"),
    ("GRASIM", "GRASIM", "Cement"),
    ("ADANIENT", "ADANIENT", "Conglomerate"),
    ("ADANIPORTS", "ADANIPORTS", "Ports"),
    ("POWERGRID", "POWERGRID", "Power"),
    ("NTPC", "NTPC", "Power"),
    ("TATAPOWER", "TATAPOWER", "Power"),
    ("COALINDIA", "COALINDIA", "Mining"),
    ("ONGC", "ONGC", "Oil & Gas"),
    ("BPCL", "BPCL", "Oil & Gas"),
    ("JSWSTEEL", "JSWSTEEL", "Steel"),
    ("TATASTEEL", "TATASTEEL", "Steel"),
    ("HINDALCO", "HINDALCO", "Metals"),
    ("BAJFINANCE", "BAJFINANCE", "Finance"),
    ("BAJAJFINSV", "BAJAJFINSV", "Finance"),
    ("HDFCLIFE", "HDFCLIFE", "Insurance"),
    ("SBILIFE", "SBILIFE", "Insurance"),
    ("BRITANNIA", "BRITANNIA", "FMCG"),
    ("TRENT", "TRENT", "Retail"),
    ("ETERNAL", "ETERNAL", "Consumer Tech"),
]


# ──────────────────────── ENV LOADER ────────────────────────
def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


# ──────────────────────── UNIFIED DATA STORE ────────────────────────
# data[(company, year)] = {PE, ROE, ROCE, Current_Ratio, Debt_Equity, Sector, source_*}
data_store: dict[tuple[str, int], dict[str, Any]] = {}


def store(company: str, year: int, field: str, value: Any, source: str):
    key = (company, year)
    if key not in data_store:
        data_store[key] = {}
    rec = data_store[key]
    # Only overwrite if current value is None or missing
    if rec.get(field) is None:
        rec[field] = value
        rec[f"source_{field}"] = source


# ──────────────────────── SOURCE 1: INDIANAPI.IN ────────────────────────
def fetch_indianapi(env: dict):
    api_key = env.get("INDIANAPI_API_KEY", "")
    if not api_key:
        print("[IndianAPI] No API key found, skipping")
        return
    base = "https://stock.indianapi.in"
    hdrs = {"x-api-key": api_key}

    for ticker, _, sector in COMPANIES:
        # -- PE historical --
        print(f"  [IndianAPI] {ticker}: fetching PE history...", end=" ")
        try:
            for attempt in range(3):
                r = requests.get(f"{base}/historical_data",
                                 params={"stock_name": ticker, "period": "max", "filter": "pe"},
                                 headers=hdrs, timeout=30)
                if r.status_code == 429:
                    wait = 5 * (attempt + 1)
                    print(f"rate-limited, waiting {wait}s...", end=" ")
                    time.sleep(wait)
                    continue
                break
            if r.status_code == 200:
                datasets = r.json().get("datasets", [])
                pe_dataset = next((d for d in datasets if d.get("metric") == "Price to Earning"), None)
                if pe_dataset:
                    # Extract annual PE (use March value for Indian FY)
                    yearly_pe: dict[int, list[float]] = {}
                    for pt in pe_dataset.get("values", []):
                        date_str, val = pt[0], pt[1]
                        yr = int(date_str[:4])
                        if isinstance(val, str):
                            try: val = float(val)
                            except: continue
                        if val and yr in YEAR_RANGE:
                            yearly_pe.setdefault(yr, []).append(val)
                    # Use median PE for each year
                    count = 0
                    for yr, vals in yearly_pe.items():
                        vals.sort()
                        median = vals[len(vals) // 2]
                        store(ticker, yr, "PE", round(median, 2), "IndianAPI")
                        count += 1
                    print(f"{count} years of PE")
                else:
                    print("no PE dataset")
            else:
                print(f"HTTP {r.status_code}")
        except Exception as e:
            print(f"error: {e}")

        # Use registry sector (skip /stock to save API quota)
        for yr in YEAR_RANGE:
            store(ticker, yr, "Sector", sector, "Registry")

        time.sleep(1.5)  # Rate limiting — respect free tier


# ──────────────────────── SOURCE 2: SCREENER.IN (direct scrape) ────────────────────────
def fetch_screener(env: dict):
    for ticker, slug, _ in COMPANIES:
        url = f"https://www.screener.in/company/{slug}/consolidated/"
        print(f"  [Screener] {ticker}: scraping...", end=" ")
        try:
            r = requests.get(url, headers=HEADERS_BROWSER, timeout=30)
            if r.status_code != 200:
                # Try standalone
                url = f"https://www.screener.in/company/{slug}/"
                r = requests.get(url, headers=HEADERS_BROWSER, timeout=30)
            if r.status_code != 200:
                print(f"HTTP {r.status_code}")
                continue

            soup = BeautifulSoup(r.text, "html.parser")
            year_cols = _parse_year_columns(soup)
            if not year_cols:
                print("no year columns found")
                continue

            # ROCE from ratios table
            _parse_ratio_row(soup, "ratios", "ROCE %", ticker, "ROCE", year_cols)
            # ROE directly from ratios table (banks have this!)
            _parse_ratio_row(soup, "ratios", "ROE %", ticker, "ROE", year_cols)

            # Balance sheet for Debt/Equity
            bs_data = _parse_section_table(soup, "balance-sheet", year_cols)
            # P&L for ROE (fallback derivation for non-banks)
            pl_data = _parse_section_table(soup, "profit-loss", year_cols)

            count = 0
            for yr in year_cols.values():
                # Find values with flexible label matching (labels have trailing +)
                borrowings = _find_bs(bs_data, "Borrowings", yr) or _find_bs(bs_data, "Borrowing", yr)
                equity = _find_bs(bs_data, "Equity Capital", yr)
                reserves = _find_bs(bs_data, "Reserves", yr)
                net_profit = _find_bs(pl_data, "Net Profit", yr)

                # Debt/Equity = Borrowings / (Equity Capital + Reserves)
                if borrowings is not None and equity is not None and reserves is not None:
                    denom = equity + reserves
                    if denom > 0:
                        de = round(borrowings / denom, 2)
                        store(ticker, yr, "Debt_Equity", de, "Screener")
                        count += 1

                # ROE = Net Profit / (Equity Capital + Reserves) * 100 (fallback if not from ratios)
                if net_profit is not None and equity is not None and reserves is not None:
                    denom = equity + reserves
                    if denom > 0:
                        roe = round((net_profit / denom) * 100, 2)
                        store(ticker, yr, "ROE", roe, "Screener")

            print(f"done ({count} yrs D/E)")
        except Exception as e:
            print(f"error: {e}")
        time.sleep(1.0)


def _parse_year_columns(soup) -> dict[int, int]:
    """Parse column headers like 'Mar 2015' -> {col_index: year}."""
    mapping = {}
    # Find first table header row in any section
    for section_id in ["ratios", "profit-loss", "balance-sheet"]:
        sec = soup.find("section", id=section_id)
        if not sec:
            continue
        table = sec.find("table")
        if not table:
            continue
        header_row = table.find("tr")
        if header_row:
            for i, th in enumerate(header_row.find_all(["th", "td"])):
                txt = th.get_text(strip=True)
                m = re.match(r"Mar\s+(\d{4})", txt)
                if m:
                    yr = int(m.group(1))
                    if 2000 <= yr <= 2030:
                        mapping[i] = yr
            if mapping:
                return mapping
    return mapping


def _parse_num(txt: str) -> float | None:
    txt = txt.strip().replace(",", "").replace("%", "")
    if not txt or txt == "--":
        return None
    try:
        return float(txt)
    except ValueError:
        return None


def _parse_ratio_row(soup, section_id: str, metric: str, ticker: str, field: str, year_cols: dict):
    sec = soup.find("section", id=section_id)
    if not sec:
        return
    table = sec.find("table")
    if not table:
        return
    for row in table.find_all("tr"):
        cells = row.find_all(["th", "td"])
        if not cells:
            continue
        label = cells[0].get_text(strip=True)
        if metric.lower() in label.lower():
            for i, cell in enumerate(cells):
                if i in year_cols:
                    val = _parse_num(cell.get_text(strip=True))
                    if val is not None:
                        store(ticker, year_cols[i], field, val, "Screener")


def _parse_section_table(soup, section_id: str, year_cols: dict) -> dict[tuple[str, int], float]:
    result = {}
    sec = soup.find("section", id=section_id)
    if not sec:
        return result
    table = sec.find("table")
    if not table:
        return result
    for row in table.find_all("tr"):
        cells = row.find_all(["th", "td"])
        if not cells:
            continue
        label = cells[0].get_text(strip=True)
        if not label:
            continue
        for i, cell in enumerate(cells):
            if i in year_cols:
                val = _parse_num(cell.get_text(strip=True))
                if val is not None:
                    result[(label, year_cols[i])] = val
    return result


def _find_bs(data: dict, prefix: str, yr: int) -> float | None:
    """Find value in parsed table data, matching labels like 'Net Profit+' or 'Net Profit'."""
    for label_suffix in ["", "+", " +"]:
        val = data.get((prefix + label_suffix, yr))
        if val is not None:
            return val
    return None


# ──────────────────────── SOURCE 3: SCREENER APIFY ────────────────────────
def fetch_apify(env: dict):
    url = env.get("APIFY_GET_DATASETITEMS_API_KEY", "")
    if not url:
        print("[Apify] No dataset URL found, skipping")
        return
    print(f"  [Apify] Fetching existing dataset...", end=" ")
    try:
        r = requests.get(url, timeout=90)
        items = r.json()
        print(f"{len(items)} companies")
        for item in items:
            name = item.get("company_name", "")
            # Try to match to our ticker list
            ticker = _match_apify_company(name)
            if not ticker:
                print(f"    Skipping unmapped company: {name}")
                continue

            # ROCE from ratios
            for ratio in item.get("ratios", []):
                if ratio.get("Metric") == "ROCE %":
                    for k, v in ratio.items():
                        if k == "Metric":
                            continue
                        m = re.match(r"Mar\s+(\d{4})", k)
                        if m and v is not None:
                            yr = int(m.group(1))
                            store(ticker, yr, "ROCE", v, "Apify")

            # Balance sheet for Debt/Equity
            bs_metrics = {}
            for row in item.get("balance_sheet", []):
                metric = row.get("Metric", "")
                for k, v in row.items():
                    if k == "Metric":
                        continue
                    m = re.match(r"Mar\s+(\d{4})", k)
                    if m and v is not None:
                        yr = int(m.group(1))
                        bs_metrics[(metric, yr)] = v

            for yr in YEAR_RANGE:
                borr = bs_metrics.get(("Borrowings", yr))
                eq = bs_metrics.get(("Equity Capital", yr))
                res = bs_metrics.get(("Reserves", yr))
                if borr is not None and eq is not None and res is not None:
                    denom = eq + res
                    if denom > 0:
                        store(ticker, yr, "Debt_Equity", round(borr / denom, 2), "Apify")

            print(f"    Loaded {ticker} from Apify")
    except Exception as e:
        print(f"error: {e}")


def _match_apify_company(name: str) -> str | None:
    name_lower = name.lower()
    mapping = {
        "tata consultancy": "TCS",
        "reliance industries": "RELIANCE",
        "infosys": "INFY",
        "hdfc bank": "HDFCBANK",
        "icici bank": "ICICIBANK",
        "state bank": "SBIN",
    }
    for fragment, ticker in mapping.items():
        if fragment in name_lower:
            return ticker
    return None


# ──────────────────────── SOURCE 4: MONEYCONTROL (fallback) ────────────────────────
MC_SLUG_MAP = {
    "RELIANCE": ("relianceindustries", "RI"),
    "TCS": ("tataconsultancyservices", "TCS"),
    "HDFCBANK": ("haborafcbank", "HDF01"),
    "ICICIBANK": ("icicibank", "ICI02"),
    "SBIN": ("statebankofindia", "SBI"),
    "INFY": ("infosys", "IT"),
    "KOTAKBANK": ("kotakmahindrabank", "KMB"),
    "AXISBANK": ("axisbank", "AB16"),
    "ITC": ("itc", "ITC"),
    "LT": ("larsentoubro", "LT"),
    "BHARTIARTL": ("bhartiairtel", "BA08"),
    "BAJFINANCE": ("bajajfinance", "BAF"),
    "MARUTI": ("marutisuzukiindia", "MS24"),
    "SUNPHARMA": ("sunpharmaceuticalindustries", "SPI"),
    "TATAMOTORS": ("tatamotors", "TM03"),
    "HINDUNILVR": ("hindustanunilever", "HU"),
    "NTPC": ("ntpc", "NTP"),
    "POWERGRID": ("powergridcorporationofindia", "PGC"),
    "TATASTEEL": ("tatasteel", "TIS"),
    "COALINDIA": ("coalindia", "CI11"),
    "ONGC": ("oilnaturalgascorporation", "ONG"),
    "WIPRO": ("wipro", "W05"),
}


def fetch_moneycontrol():
    """Fallback: scrape MoneyControl for Current_Ratio + gap-fill (requires Playwright)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[MoneyControl] Playwright not installed, skipping")
        return

    companies_to_scrape = []
    for ticker, _, _ in COMPANIES:
        if ticker not in MC_SLUG_MAP:
            continue
        # Check if we're missing data for any year
        missing = any(
            data_store.get((ticker, yr), {}).get("Current_Ratio") is None
            for yr in YEAR_RANGE
        )
        if missing:
            companies_to_scrape.append(ticker)

    if not companies_to_scrape:
        print("[MoneyControl] No gaps to fill")
        return

    print(f"  [MoneyControl] Scraping {len(companies_to_scrape)} companies...")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
            ctx = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1366, "height": 768},
            )
            page = ctx.new_page()
            page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            )

            for ticker in companies_to_scrape:
                slug, code = MC_SLUG_MAP[ticker]
                print(f"    [MC] {ticker}...", end=" ")
                count = 0
                try:
                    # Paginate: page 1 = /ratiosVI/CODE, page 2 = /ratiosVI/CODE/2, etc.
                    for pg in range(1, 6):  # up to 5 pages = 25 years
                        if pg == 1:
                            url = f"https://www.moneycontrol.com/financials/{slug}/ratiosVI/{code}#RI"
                        else:
                            url = f"https://www.moneycontrol.com/financials/{slug}/ratiosVI/{code}/{pg}#RI"

                        page.goto(url, wait_until="domcontentloaded", timeout=20000)
                        time.sleep(4)

                        if "Access Denied" in page.title():
                            print("blocked!", end=" ")
                            break

                        n = _parse_mc_ratios(page, ticker)
                        count += n
                        if n == 0:
                            break  # No more data on this page

                    print(f"{count} data points")
                except Exception as e:
                    print(f"error: {e}")
                time.sleep(2)

            browser.close()
    except Exception as e:
        print(f"[MoneyControl] Playwright error: {e}")


def _parse_mc_ratios(page, ticker: str) -> int:
    """Parse MoneyControl ratio table. Returns number of data points stored."""
    stored = 0
    try:
        table = page.query_selector("table.mctable1")
        if not table:
            return 0
        rows = table.query_selector_all("tr")
        years: list[int] = []

        for row in rows:
            cells = row.query_selector_all("th, td")
            texts = [c.inner_text().strip() for c in cells]
            if not texts:
                continue
            label = texts[0]

            # Parse year header
            if "KEY FINANCIAL" in label.upper():
                for t in texts[1:]:
                    m = re.match(r"MAR\s+(\d{2,4})", t, re.I)
                    if m:
                        yr = int(m.group(1))
                        if yr < 100:
                            yr += 2000
                        years.append(yr)
                continue

            if not years:
                continue

            label_lower = label.lower()
            field = None
            if "current ratio" in label_lower:
                field = "Current_Ratio"
            elif "return on equity" in label_lower or "return on net worth" in label_lower:
                field = "ROE"
            elif "return on capital employed" in label_lower:
                field = "ROCE"
            elif "debt/equity" in label_lower or "debt equity" in label_lower:
                field = "Debt_Equity"

            if field:
                for i, yr in enumerate(years):
                    idx = i + 1
                    if idx < len(texts):
                        val_str = texts[idx].strip().replace(",", "")
                        try:
                            val = float(val_str) if val_str and val_str != "--" else None
                        except ValueError:
                            val = None
                        if val is not None and yr in YEAR_RANGE:
                            store(ticker, yr, field, val, "MoneyControl")
                            stored += 1
    except Exception:
        pass
    return stored


# ──────────────────────── OUTPUT ────────────────────────
def save_csv():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fields = ["Year", "Company", "Sector", "PE", "ROE", "ROCE", "Current_Ratio", "Debt_Equity"]
    rows = []
    for ticker, _, default_sector in COMPANIES:
        for yr in YEAR_RANGE:
            rec = data_store.get((ticker, yr), {})
            rows.append({
                "Year": yr,
                "Company": ticker,
                "Sector": rec.get("Sector", default_sector),
                "PE": rec.get("PE"),
                "ROE": rec.get("ROE"),
                "ROCE": rec.get("ROCE"),
                "Current_Ratio": rec.get("Current_Ratio"),
                "Debt_Equity": rec.get("Debt_Equity"),
            })

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n{'='*60}")
    print(f"Saved {len(rows)} rows to {OUTPUT_CSV}")
    print(f"{'='*60}")

    # Coverage stats
    total = len(rows)
    for col in ["PE", "ROE", "ROCE", "Current_Ratio", "Debt_Equity"]:
        filled = sum(1 for r in rows if r[col] is not None)
        pct = (filled / total * 100) if total else 0
        print(f"  {col:15s}: {filled:4d}/{total} ({pct:5.1f}%)")


# ──────────────────────── LOAD EXISTING CSV ────────────────────────
def load_existing_csv():
    """Load data from previous pipeline runs to preserve already-fetched data."""
    if not OUTPUT_CSV.exists():
        print("  No existing CSV found")
        return 0
    count = 0
    with open(OUTPUT_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ticker = row["Company"]
            yr = int(row["Year"])
            for field in ["PE", "ROE", "ROCE", "Current_Ratio", "Debt_Equity"]:
                val = row.get(field)
                if val and val.strip():
                    try:
                        store(ticker, yr, field, float(val), "cached")
                        count += 1
                    except ValueError:
                        pass
            if row.get("Sector"):
                store(ticker, yr, "Sector", row["Sector"], "cached")
    print(f"  Loaded {count} data points from existing CSV")
    return count


# ──────────────────────── MAIN ────────────────────────
def main():
    data_store.clear()
    env = load_env()
    print("=" * 60)
    print("CAP DATA PIPELINE — Nifty50 + BankNifty Ratios 2005-2025")
    print(f"Companies: {len(COMPANIES)} | Years: {YEAR_RANGE.start}-{YEAR_RANGE.stop-1}")
    print("=" * 60)

    print("\n[PHASE 0] Loading existing data from previous runs")
    load_existing_csv()

    print("\n[PHASE 1] IndianAPI.in — PE + Sector")
    api_key = env.get("INDIANAPI_API_KEY", "")
    if api_key:
        # Quick quota check — try one request
        try:
            test = requests.get("https://stock.indianapi.in/historical_data",
                                params={"stock_name": "RELIANCE", "period": "1y", "filter": "pe"},
                                headers={"x-api-key": api_key}, timeout=10)
            if test.status_code == 429:
                print("  API quota exhausted (HTTP 429) — skipping, using cached PE data")
            elif test.status_code == 200:
                fetch_indianapi(env)
            else:
                print(f"  API returned HTTP {test.status_code} — skipping")
        except Exception as e:
            print(f"  API unreachable: {e} — skipping")
    else:
        print("  No API key — skipping")

    print("\n[PHASE 2] Screener.in — ROCE, ROE, Debt/Equity")
    fetch_screener(env)

    print("\n[PHASE 3] Screener Apify — Supplementary data")
    fetch_apify(env)

    print("\n[PHASE 4] MoneyControl — Current Ratio + gap fill (headed browser)")
    fetch_moneycontrol()

    print("\n[PHASE 5] Saving CSV")
    save_csv()


if __name__ == "__main__":
    main()

