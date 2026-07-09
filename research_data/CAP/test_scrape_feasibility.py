"""Quick test: Can we parse Screener.in and MoneyControl without a browser?"""
import requests
from bs4 import BeautifulSoup
import json, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ---- TEST 1: Screener.in ----
print("=" * 60)
print("TEST 1: Screener.in (direct HTML)")
print("=" * 60)
url = "https://www.screener.in/company/RELIANCE/consolidated/"
r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
print(f"Status: {r.status_code}, Size: {len(r.text)} bytes")

soup = BeautifulSoup(r.text, "html.parser")

# Look for ratio tables
sections = soup.find_all("section", id=True)
print(f"Sections with IDs: {[s.get('id') for s in sections]}")

# Check for the ratios section
ratios_section = soup.find("section", id="ratios")
if ratios_section:
    table = ratios_section.find("table")
    if table:
        rows = table.find_all("tr")
        print(f"\nRatios table: {len(rows)} rows")
        for row in rows[:8]:
            cells = [td.get_text(strip=True) for td in row.find_all(["th", "td"])]
            print(f"  {cells}")
    else:
        print("No table in ratios section")
else:
    print("No ratios section found")

# Check for PE in the company info section
top_ratios = soup.find("div", id="top-ratios")
if not top_ratios:
    top_ratios = soup.find("ul", id="top-ratios")
if top_ratios:
    items = top_ratios.find_all("li")
    print(f"\nTop ratios: {len(items)} items")
    for li in items[:10]:
        name = li.find("span", class_="name")
        value = li.find("span", class_="value") or li.find("span", class_="number")
        n = name.get_text(strip=True) if name else "?"
        v = value.get_text(strip=True) if value else li.get_text(strip=True)
        print(f"  {n}: {v}")

# Check balance sheet
bs_section = soup.find("section", id="balance-sheet")
if bs_section:
    table = bs_section.find("table")
    if table:
        rows = table.find_all("tr")
        print(f"\nBalance sheet: {len(rows)} rows")
        for row in rows[:5]:
            cells = [td.get_text(strip=True) for td in row.find_all(["th", "td"])]
            print(f"  {cells[:6]}")

# ---- TEST 2: MoneyControl internal API ----
print()
print("=" * 60)
print("TEST 2: MoneyControl internal API attempts")
print("=" * 60)

# Try known MC internal endpoints
mc_headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

# Try the API endpoint format used by their frontend
urls_to_try = [
    "https://priceapi.moneycontrol.com/techCharts/indianMarket/stock/history?symbol=RELIANCE&resolution=1D",
    "https://api.moneycontrol.com/mcapi/v1/stock/get-stock-price?scIdList=RI&ex=N",
    "https://www.moneycontrol.com/mc/widget/basicinfo/getBasicInfo?classic=true&scId=RI",
]

for url in urls_to_try:
    try:
        r = requests.get(url, headers=mc_headers, timeout=10)
        print(f"  {url.split('/')[-1][:50]}: HTTP {r.status_code} | {len(r.text)} bytes")
        if r.status_code == 200 and len(r.text) < 500:
            print(f"    Response: {r.text[:200]}")
    except Exception as e:
        print(f"  {url.split('/')[-1][:50]}: ERROR - {e}")

print("\n=== CONCLUSION ===")
print("If Screener.in data is in HTML -> we can scrape directly (no browser needed)")
print("If not -> we need Playwright/Selenium for MoneyControl")
