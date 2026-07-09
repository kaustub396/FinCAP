import csv
import shutil
import os

src = 'output/nifty_banknifty_ratios_banking.csv'
dst = 'output/nifty_banknifty_ratios_clean.csv'

# Read the source file
with open(src, 'r', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))
    fieldnames = list(rows[0].keys())

kept_rows = []
removed_rows = []

for row in rows:
    sector = row['Sector']
    pe_val = row['PE'].strip()

    # Skip pre-listing rows entirely (keep them as-is)
    if not pe_val:
        kept_rows.append(row)
        continue

    is_bank = (sector == 'Regional Banks')
    cols = ['PE', 'ROE', 'Debt_Equity', 'NIM', 'NPA_Ratio', 'CAR'] if is_bank else ['PE', 'ROE', 'ROCE', 'Current_Ratio', 'Debt_Equity']

    has_gap = any(not row[col].strip() for col in cols)

    if has_gap:
        removed_rows.append(row)
    else:
        kept_rows.append(row)

# Write the clean file
with open(dst, 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(kept_rows)

print(f'Source file:   {src}')
print(f'Output file:   {dst}')
print(f'Original rows: {len(rows)}')
print(f'Rows kept:     {len(kept_rows)}')
print(f'Rows removed:  {len(removed_rows)}')
print()
print('=== REMOVED ROWS (Company | Year | Missing Columns) ===')
for row in removed_rows:
    comp, yr, sector = row['Company'], row['Year'], row['Sector']
    is_bank = (sector == 'Regional Banks')
    cols = ['PE', 'ROE', 'Debt_Equity', 'NIM', 'NPA_Ratio', 'CAR'] if is_bank else ['PE', 'ROE', 'ROCE', 'Current_Ratio', 'Debt_Equity']
    missing = [col for col in cols if not row[col].strip()]
    print(f'  {comp} ({yr}) — Missing: {", ".join(missing)}')
