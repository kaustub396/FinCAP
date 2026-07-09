import csv

r = list(csv.DictReader(open('output/nifty_banknifty_ratios_banking.csv', 'r', encoding='utf-8')))

gaps_by_company = {}
for row in r:
    comp = row['Company']
    sector = row['Sector']
    yr = row['Year']
    if not row['PE'].strip():
        continue
    is_bank = (sector == 'Regional Banks')
    cols = ['PE', 'ROE', 'Debt_Equity', 'NIM', 'NPA_Ratio', 'CAR'] if is_bank else ['PE', 'ROE', 'ROCE', 'Current_Ratio', 'Debt_Equity']
    for col in cols:
        if not row[col].strip():
            if comp not in gaps_by_company:
                gaps_by_company[comp] = {'sector': sector, 'gaps': []}
            gaps_by_company[comp]['gaps'].append((yr, col))

print('=== GAPS BY COMPANY ===')
for comp, info in sorted(gaps_by_company.items()):
    sec = info['sector']
    print(f'\n{comp} ({sec}):')
    for yr, col in info['gaps']:
        print(f'  {yr} - {col}')

total = sum(len(v['gaps']) for v in gaps_by_company.values())
print(f'\n=== TOTAL GAPS: {total} ===')
print(f'=== OUT OF 5581 APPLICABLE CELLS ===')
print(f'=== REMAINING COMPLETION: {(5581 - total) / 5581 * 100:.2f}% ===')
