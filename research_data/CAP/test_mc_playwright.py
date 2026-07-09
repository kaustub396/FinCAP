"""MC: investigate how prevpaging works — check its href/onclick."""
import sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

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
    
    url = "https://www.moneycontrol.com/financials/relianceindustries/ratiosVI/RI#RI"
    print(f"Navigating to {url}...")
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    print(f"Page title: {page.title()}")
    time.sleep(5)
    
    table = page.query_selector("table.mctable1")
    print(f"Table exists: {table is not None}")
    
    # Find all table elements on the page
    tables = page.query_selector_all("table")
    print(f"Total tables: {len(tables)}")
    # Let's inspect the last table, which seems to contain the indicators and ratios
    if len(tables) > 3:
        target_table = tables[3]
        rows = target_table.query_selector_all("tr")
        print(f"Target table has {len(rows)} rows.")
        for r_idx, r in enumerate(rows[:20]): # Show first 20 rows
            cells = r.query_selector_all("td, th")
            texts = [c.inner_text().strip() for c in cells]
            print(f"Row {r_idx}: {texts}")
    
    # Get the prevpaging element details
    prev = page.query_selector(".prevpaging")
    if prev:
        tag = prev.evaluate("el => el.tagName")
        html = prev.evaluate("el => el.outerHTML")
        href = prev.get_attribute("href")
        onclick = prev.get_attribute("onclick")
        parent_html = prev.evaluate("el => el.parentElement.outerHTML.substring(0, 500)")
        print(f"Tag: {tag}")
        print(f"HTML: {html}")
        print(f"href: {href}")
        print(f"onclick: {onclick}")
        print(f"Parent: {parent_html}")
    
    # Also look for "nextpaging"
    nxt = page.query_selector(".nextpaging")
    if nxt:
        print(f"\nnextpaging HTML: {nxt.evaluate('el => el.outerHTML')}")
    
    # Check if there's a dropdown or select for year range
    selects = page.query_selector_all("select")
    for s in selects:
        name = s.get_attribute("name") or s.get_attribute("id") or ""
        opts = s.query_selector_all("option")
        opt_texts = [o.inner_text().strip() for o in opts[:10]]
        print(f"\nSelect '{name}': {opt_texts}")
    
    # Check for the year navigation links within the page
    # MC often uses links like "/ratiosVI/RI" where VI = page number
    links = page.query_selector_all("a[href*='ratios']")
    for a in links:
        href = a.get_attribute("href") or ""
        txt = a.inner_text().strip()[:30]
        if "ratio" in href.lower() and "RI" in href:
            print(f"\nRatios link: '{txt}' -> {href}")
    
    browser.close()
