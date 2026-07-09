"""Verify corrected MC slugs before updating the scraper."""
import sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

FIXES = {
    "HCLTECH":     ("hcltechnologies", "HCL02"),
    "EICHERMOT":   ("eichermotors", "EM"),
    "ULTRACEMCO":  ("ultratechcement", "UTC"),
    "HDFCLIFE":    ("hdfclifeinsurancecompany", "HLI"),
    "SBILIFE":     ("sbilifeinsurancecompany", "SLI02"),
    "HDFCBANK":    ("hdfcbank", "HDF01"),
    "INDUSINDBK":  ("indusindbank", "IIB"),
    "JSWSTEEL":    ("jswsteel", "JSW01"),
    "LT":          ("larsentoubro", "LT"),
    "DRREDDY":     ("drreddyslaboratories", "DRL"),
}

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False,
        args=["--disable-blink-features=AutomationControlled","--no-sandbox"])
    ctx = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        viewport={"width":1366,"height":768})
    page = ctx.new_page()
    page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")

    results = {}
    for ticker, (slug, code) in FIXES.items():
        url = f"https://www.moneycontrol.com/financials/{slug}/ratiosVI/{code}#RI"
        print(f"  {ticker}: {url}... ", end="")
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            time.sleep(3)
            title = page.title()
            if "Access Denied" in title:
                print("BLOCKED")
                results[ticker] = "BLOCKED"
            elif "Top News" in title or "Page Not Found" in title:
                print(f"NOT FOUND ({title[:40]})")
                results[ticker] = "NOT_FOUND"
            else:
                table = page.query_selector("table.mctable1")
                rows = table.query_selector_all("tr") if table else []
                print(f"OK - {len(rows)} rows - {title[:50]}")
                results[ticker] = f"OK ({len(rows)} rows)"
        except Exception as e:
            print(f"ERROR: {e}")
            results[ticker] = "ERROR"
        time.sleep(2)

    browser.close()

print(f"\n{'='*50}")
print("VERIFICATION RESULTS")
print(f"{'='*50}")
ok = sum(1 for v in results.values() if v.startswith("OK"))
print(f"  {ok}/{len(FIXES)} slugs verified OK")
for t, r in results.items():
    status = "✓" if r.startswith("OK") else "✗"
    print(f"  {status} {t}: {r}")
