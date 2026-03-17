import pandas as pd
import re

pm_df = pd.read_csv('exports/mineral_rights_pm_wide.csv')
event_date = '2025-03-24'
event_year, event_month, event_day = event_date.split('-')

# Extract dates
time_cols = [col for col in pm_df.columns if col.startswith('outcome_') and ('open_0500_PT' in col or 'close_1700_PT' in col)]
dates = set()
for col in time_cols:
    match = re.search(r'(\d{4})_(\d{2})_(\d{2})_(open_0500_PT|close_1700_PT)', col)
    if match:
        dates.add((match.group(1), match.group(2), match.group(3), match.group(4)))

sorted_dates = sorted(dates, key=lambda x: (x[0], x[1], x[2], 0 if x[3] == 'open_0500_PT' else 1))
pre_event_dates = [d for d in sorted_dates if (d[0], d[1], d[2]) < (event_year, event_month, event_day)]

print(f'Total pre-event dates: {len(pre_event_dates)}')
print(f'Pre-event dates: {pre_event_dates}\n')

# Analyze each market
passing = 0
for idx in range(min(10, len(pm_df))):
    row = pm_df.iloc[idx]
    
    pre_prices_0 = []
    pre_prices_1 = []
    col_0_base = None
    col_1_base = None
    
    for d in pre_event_dates:
        suffix = f'_{d[0]}_{d[1]}_{d[2]}_{d[3]}'
        col_0_candidates = [col for col in pm_df.columns if col.startswith('outcome_0_') and col.endswith(suffix)]
        col_1_candidates = [col for col in pm_df.columns if col.startswith('outcome_1_') and col.endswith(suffix)]
        
        if col_0_candidates and col_1_candidates:
            col_0 = col_0_candidates[0]
            col_1 = col_1_candidates[0]
            
            if pd.notna(row[col_0]) and pd.notna(row[col_1]):
                pre_prices_0.append(row[col_0])
                pre_prices_1.append(row[col_1])
                
                if col_0_base is None:
                    parts_0 = col_0.replace(suffix, '').replace('outcome_0_', '')
                    parts_1 = col_1.replace(suffix, '').replace('outcome_1_', '')
                    col_0_base = parts_0
                    col_1_base = parts_1
            else:
                break
        else:
            break
    
    if len(pre_prices_0) == len(pre_event_dates):
        all_o0_gt = all(p > 0.5 for p in pre_prices_0)
        all_o1_gt = all(p > 0.5 for p in pre_prices_1)
        
        print(f'Market {idx}:')
        print(f'  Pre-event o0: {[f"{p:.3f}" for p in pre_prices_0]}')
        print(f'  Pre-event o1: {[f"{p:.3f}" for p in pre_prices_1]}')
        print(f'  All o0 > .5? {all_o0_gt}')
        print(f'  All o1 > .5? {all_o1_gt}')
        print(f'  col_0_base: {col_0_base}')
        print(f'  col_1_base: {col_1_base}')
        
        if all_o0_gt or all_o1_gt:
            passing += 1
            print(f'  *** PASSES ***')
        print()

print(f'Total passing strict: {passing}')
