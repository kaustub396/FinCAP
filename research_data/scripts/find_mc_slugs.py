"""Find MoneyControl slugs for all companies using MC search."""
import sys, time, re, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

COMPANIES = [
    "AUBANK", "AXISBANK", "BANDHANBNK", "BANKBARODA", "CANBK",
    "FEDERALBNK", "HDFCBANK", "ICICIBANK", "IDFCFIRSTB", "INDUSINDBK",
    "KOTAKBANK", "PNB", "RBLBANK", "SBIN",
    "RELIANCE", "TCS", "INFY", "HCLTECH", "WIPRO", "TECHM",
    "LT", "ITC", "HINDUNILVR", "NESTLEIND", "BHARTIARTL",
    "SUNPHARMA", "DRREDDY", "CIPLA", "APOLLOHOSP", "MARUTI",
    "TATAMOTORS", "M&M", "BAJAJ-AUTO", "EICHERMOT", "HEROMOTOCO",
    "TITAN", "ASIANPAINT", "ULTRACEMCO", "SHREECEM", "GRASIM",
    "ADANIENT", "ADANIPORTS", "POWERGRID", "NTPC", "TATAPOWER",
    "COALINDIA", "ONGC", "BPCL", "JSWSTEEL", "TATASTEEL",
    "HINDALCO", "BAJFINANCE", "BAJAJFINSV", "HDFCLIFE", "SBILIFE",
    "BRITANNIA", "TRENT", "ETERNAL",
]

# Map NSE ticker -> MC search term
SEARCH_TERMS = {
    "AUBANK": "AU Small Finance Bank",
    "BANDHANBNK": "Bandhan Bank",
    "BANKBARODA": "Bank of Baroda",
    "CANBK": "Canara Bank",
    "FEDERALBNK": "Federal Bank",
    "IDFCFIRSTB": "IDFC First Bank",
    "INDUSINDBK": "IndusInd Bank",
    "KOTAKBANK": "Kotak Mahindra Bank",
    "PNB": "Punjab National Bank",
    "RBLBANK": "RBL Bank",
    "HCLTECH": "HCL Technologies",
    "TECHM": "Tech Mahindra",
    "HINDUNILVR": "Hindustan Unilever",
    "NESTLEIND": "Nestle India",
    "BHARTIARTL": "Bharti Airtel",
    "SUNPHARMA": "Sun Pharma",
    "DRREDDY": "Dr Reddy",
    "APOLLOHOSP": "Apollo Hospitals",
    "TATAMOTORS": "Tata Motors",
    "M&M": "Mahindra Mahindra",
    "BAJAJ-AUTO": "Bajaj Auto",
    "EICHERMOT": "Eicher Motors",
    "HEROMOTOCO": "Hero MotoCorp",
    "ASIANPAINT": "Asian Paints",
    "ULTRACEMCO": "UltraTech Cement",
    "SHREECEM": "Shree Cement",
    "ADANIENT": "Adani Enterprises",
    "ADANIPORTS": "Adani Ports",
    "POWERGRID": "Power Grid",
    "TATAPOWER": "Tata Power",
    "COALINDIA": "Coal India",
    "JSWSTEEL": "JSW Steel",
    "TATASTEEL": "Tata Steel",
    "BAJFINANCE": "Bajaj Finance",
    "BAJAJFINSV": "Bajaj Finserv",
    "HDFCLIFE": "HDFC Life",
    "SBILIFE": "SBI Life",
    "ETERNAL": "Eternal",
}

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
    
    slug_map = {}
    
    for ticker in COMPANIES:
        search = SEARCH_TERMS.get(ticker, ticker)
        print(f"{ticker} ({search}): ", end="")
        
        try:
            # Navigate to MC ratios via search redirect
            url = f"https://www.moneycontrol.com/stocks/cptmarket/compsearch.php?search_data=&cid=&mbsearch_str={search.replace(' ', '+')}&topsearch_type=1&search_str={search.replace(' ', '+')}"
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            time.sleep(3)
            
            current = page.url
            # Extract company slug from URL
            # Format: /india/stockpricequote/industry/company-name/CODE
            m = re.search(r'/stockpricequote/[^/]+/([^/]+)/([^/#?]+)', current)
            if m:
                slug = m.group(1)
                code = m.group(2)
                slug_map[ticker] = (slug, code)
                print(f"slug={slug}, code={code}")
            else:
                # Try to find ratios link on the page
                ratios_link = page.query_selector("a[href*='ratios']")
                if ratios_link:
                    href = ratios_link.get_attribute("href") or ""
                    m2 = re.search(r'/financials/([^/]+)/ratios[^/]*/([^/#?]+)', href)
                    if m2:
                        slug_map[ticker] = (m2.group(1), m2.group(2))
                        print(f"from ratios link: {m2.group(1)}/{m2.group(2)}")
                    else:
                        print(f"ratios link but no match: {href[:80]}")
                else:
                    print(f"no match, URL: {current[:80]}")
        except Exception as e:
            print(f"error: {e}")
        
        time.sleep(1)
    
    browser.close()

# Print final map
print("\n\n# === MC_SLUG_MAP for cap_data_pipeline.py ===")
print("MC_SLUG_MAP = {")
for ticker in COMPANIES:
    if ticker in slug_map:
        slug, code = slug_map[ticker]
        print(f'    "{ticker}": ("{slug}", "{code}"),')
    else:
        print(f'    # "{ticker}": MISSING')
print("}")
