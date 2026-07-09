"""Run MoneyControl scraper for ALL companies in MC_SLUG_MAP to fill gaps."""
import cap_data_pipeline as p

env = p.load_env()
p.data_store.clear()

print("=" * 60)
print("MC GAP-FILL RUN")
print("=" * 60)

print("\n[PHASE 0] Loading existing data")
p.load_existing_csv()

print("\n[PHASE 1-3] Skipping (already done)")

print("\n[PHASE 4] MoneyControl — ALL companies")
p.fetch_moneycontrol()

print("\n[PHASE 5] Saving CSV")
p.save_csv()
