"""Check what exact row labels MC has for RELIANCE ratios page."""
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
    
    page.goto("https://www.moneycontrol.com/financials/relianceindustries/ratiosVI/RI#RI",
              wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    
    table = page.query_selector("table.mctable1")
    rows = table.query_selector_all("tr")
    for row in rows:
        cells = row.query_selector_all("td, th")
        texts = [c.inner_text().strip() for c in cells]
        if texts:
            label = texts[0]
            vals = texts[1:3] if len(texts) > 2 else texts[1:]
            print(f"  {label:45s} | {vals}")
    
    browser.close()
