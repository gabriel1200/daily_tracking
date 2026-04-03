import pandas as pd
from pathlib import Path

def print_seasonal_audit(player_id):
    # Path to the specific player's career log
    file_path = Path("careerlogs") / f"{player_id}.csv"
    
    if not file_path.exists():
        print(f"File not found: {file_path}")
        return

    # Load data
    df = pd.read_csv(file_path, low_memory=False)
    
    # Ensure 'year' is treated as an integer for clean grouping
    # If your files use 'season', swap 'year' for 'season' below
    df['year'] = pd.to_numeric(df['year'], errors='coerce')

    # 1. Identify columns that have gaps at any point in the career
    # We ignore 'Rock Solid' columns to keep the output readable
    null_counts = df.isnull().sum()
    gappy_cols = null_counts[null_counts > 0].index.tolist()

    if not gappy_cols:
        print(f"No gaps found for Player {player_id}. All columns are 100% complete.")
        return

    # 2. Group by year and calculate % missing for each gappy column
    # We use lambda to get the mean of nulls (0.0 to 1.0) and multiply by 100
    seasonal_gaps = df.groupby('year')[gappy_cols].apply(lambda x: x.isnull().mean() * 100)

    print(f"\n{'='*80}")
    print(f"SEASONAL GAP AUDIT FOR PLAYER ID: {player_id}")
    print(f"Values represent % of games missing that column")
    print(f"{'='*80}")

    # 3. Display the results
    # We sort the index (years) to see the chronological progression
    report = seasonal_gaps.sort_index()
    
    # Optional: If there are too many columns, we just show the first 15 gappy ones
    # or you can filter for specific prefixes like 'hustle_' or 'speed_'
    pd.set_option('display.max_columns', 20)
    pd.set_option('display.width', 1000)
    
    print(report)

    # 4. Summary of Introduction Years
    print(f"\n{'-'*80}")
    print("DATA EVOLUTION SUMMARY (When stats started appearing):")
    for col in gappy_cols:
        # Find the first year where the missing percentage drops significantly (e.g., below 50%)
        available_years = report[report[col] < 50].index
        if not available_years.empty:
            print(f" - {col:30} first became available in: {int(available_years.min())}")
        else:
            print(f" - {col:30} is consistently missing (>50%) across all years.")

# Run the seasonal audit for LeBron
print_seasonal_audit(2544)