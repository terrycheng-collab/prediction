import pandas as pd
import re

# Load mineral_rights PM data
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
print(f'Pre-event dates: {pre_event_dates}')
print(f'\nTotal markets: {len(pm_df)}')

# Analyze each market's pre-event prices
passers = 0
for idx, row in pm_df.iterrows():
    all_o0_gt = True
    all_o1_gt = True
    
    for d in pre_event_dates:
        suffix = f'_{d[0]}_{d[1]}_{d[2]}_{d[3]}'
        col_0_candidates = [col for col in pm_df.columns if col.startswith('outcome_0_') and col.endswith(suffix)]
        col_1_candidates = [col for col in pm_df.columns if col.startswith('outcome_1_') and col.endswith(suffix)]
        
        # Find the pair that sums to ~1
        found = False
        for c0 in col_0_candidates:
            for c1 in col_1_candidates:
                if pd.notna(row[c0]) and pd.notna(row[c1]):
                    if abs((row[c0] + row[c1]) - 1.0) < 0.01:
                        v0, v1 = row[c0], row[c1]
                        if v0 <= 0.5:
                            all_o0_gt = False
                        if v1 <= 0.5:
                            all_o1_gt = False
                        found = True
                        break
            if found:
                break
        if not found:
            all_o0_gt = False
            all_o1_gt = False
            break
    
    if all_o0_gt or all_o1_gt:
        passers += 1
        print(f'Market {idx} PASSES: all_o0_gt={all_o0_gt}, all_o1_gt={all_o1_gt}')

print(f'\nMarkets passing strict filter: {passers}')
