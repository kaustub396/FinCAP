"""Check Yearly Results page and also test PE derivation from Earnings Yield."""
import sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False,
        args=["--disable-blink-features=AutomationControlled","--no-sandbox"])
    ctx = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        viewport={"width":1366,"height":768})
    page = ctx.new_page()
    page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
    
    # Check Yearly Results page
    print("=== YEARLY RESULTS PAGE ===")
    page.goto("https://www.moneycontrol.com/financials/itc/results/yearly/ITC#ITC",
              wait_until="domcontentloaded", timeout=20000)
    time.sleep(5)
    print(f"Title: {page.title()}")
    
    table = page.query_selector("table.mctable1")
    if table:
        rows = table.query_selector_all("tr")
        print(f"Rows: {len(rows)}")
        for row in rows:
            cells = row.query_selector_all("td, th")
            texts = [c.inner_text().strip() for c in cells]
            if texts:
                label = texts[0]
                vals = texts[1:4] if len(texts) > 3 else texts[1:]
                ll = label.lower()
                if any(k in ll for k in ["p/e", "pe", "price", "earn", "eps", "yield", "valuat"]):
                    print(f"  >>> {label:50s} | {vals}")
                elif any(k in ll for k in ["key", "result", "ratio", "share"]):
                    print(f"  --- {label:50s} | {vals}")
    else:
        tables = page.query_selector_all("table")
        print(f"No mctable1, found {len(tables)} other tables")
        for t in tables[:3]:
            rows = t.query_selector_all("tr")
            print(f"  Table ({t.get_attribute('class')}): {len(rows)} rows")
            for row in rows[:5]:
                cells = row.query_selector_all("td, th")
                texts = [c.inner_text().strip()[:30] for c in cells[:5]]
                print(f"    {texts}")
    
    # Now check ratios page — get Earnings Yield values and derive PE
    print("\n=== DERIVING PE FROM EARNINGS YIELD (Ratios page) ===")
    page.goto("https://www.moneycontrol.com/financials/itc/ratiosVI/ITC#ITC",
              wait_until="domcontentloaded", timeout=20000)
    time.sleep(4)
    
    import re
    table = page.query_selector("table.mctable1")
    rows = table.query_selector_all("tr")
    years = []
    
    for row in rows:
        cells = row.query_selector_all("td, th")
        texts = [c.inner_text().strip() for c in cells]
        if not texts:
            continue
        label = texts[0]
        
        if "KEY FINANCIAL" in label.upper():
            for t in texts[1:]:
                m = re.match(r"MAR\s+(\d{2,4})", t, re.I)
                if m:
                    yr = int(m.group(1))
                    years.append(yr + 2000 if yr < 100 else yr)
        
        if "earnings yield" in label.lower() and years:
            print(f"  Earnings Yield row: {texts}")
            for i, yr in enumerate(years):
                idx = i + 1
                if idx < len(texts):
                    try:
                        ey = float(texts[idx])
                        pe = round(1.0 / ey, 2) if ey > 0 else None
                        print(f"    {yr}: EY={ey} -> PE={pe}")
                    except:
                        print(f"    {yr}: EY={texts[idx]} -> cannot parse")
    
    browser.close()
