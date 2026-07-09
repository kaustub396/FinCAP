"""Find HDFCLIFE, IDFCFIRSTB, ETERNAL on MC."""
import sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

ATTEMPTS = [
    ("HDFCLIFE", "hdfclifeinsurancecompanylimited", "HLI01"),
    ("HDFCLIFE", "hdfclifeinsurancecompanylimited", "HLI02"),
    ("HDFCLIFE", "hdfclifeinsurancecompanylimited", "HLI"),
    ("HDFCLIFE", "hdfclife", "HLI01"),
    ("HDFCLIFE", "hdfclifeinsurance", "HLI01"),
    ("IDFCFIRSTB", "idfcfirstbanklimited", "IDF02"),
    ("IDFCFIRSTB", "idfcfirstbank", "IDF"),
    ("IDFCFIRSTB", "idfcfirstbanklimited", "IDF"),
    ("IDFCFIRSTB", "idfcbank", "IDF02"),
    ("ETERNAL", "zomatolimited", "Z"),
    ("ETERNAL", "zomato", "Z"),
    ("ETERNAL", "zomatolimited", "ZOM"),
    ("ETERNAL", "eternal", "E21"),
    ("ETERNAL", "eternallimited", "E21"),
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False,
        args=["--disable-blink-features=AutomationControlled", "--no-sandbox"])
    ctx = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        viewport={"width": 1366, "height": 768})
    page = ctx.new_page()
    page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")

    found = set()
    for ticker, slug, code in ATTEMPTS:
        if ticker in found:
            continue
        url = f"https://www.moneycontrol.com/financials/{slug}/ratiosVI/{code}"
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=10000)
            time.sleep(2)
            title = page.title()
            tbl = page.query_selector("table.mctable1")
            rows = tbl.query_selector_all("tr") if tbl else []
            company = title.split(" Key ")[0] if " Key " in title else title[:50]
            status = f"{len(rows)} rows" if rows else "0 rows"
            print(f"  {ticker} ({slug}/{code}): {status} | {company}")
            if len(rows) > 5:
                found.add(ticker)
                print(f"    >>> FOUND! slug={slug}, code={code}")
        except:
            print(f"  {ticker} ({slug}/{code}): TIMEOUT")
        time.sleep(1)

    browser.close()
