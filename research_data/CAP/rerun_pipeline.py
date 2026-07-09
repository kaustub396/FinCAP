"""Final run — Screener fixes applied, skip MC (403 blocked)."""
import cap_data_pipeline as p

env = p.load_env()
print("=" * 60)
print("FINAL RUN — IndianAPI + Screener (fixed) + Apify")
print("=" * 60)

print("\n[PHASE 1] IndianAPI.in — PE + Sector")
p.fetch_indianapi(env)

print("\n[PHASE 2] Screener.in — ROCE, ROE (direct+derived), Debt/Equity (FIXED)")
p.fetch_screener(env)

print("\n[PHASE 3] Screener Apify — Supplementary data")
p.fetch_apify(env)

print("\n[PHASE 4] MoneyControl — SKIPPED (site returns 403)")

print("\n[PHASE 5] Saving CSV")
p.save_csv()
