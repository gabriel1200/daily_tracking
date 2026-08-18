import os
import re
import sys
from pathlib import Path
import pandas as pd

# 1. Setup paths relative to ~/basketball/daily_tracking
source_dir = Path("../player_sheets/game_report/all_games").resolve()
target_dir = Path("careerlogs").resolve()
target_dir.mkdir(parents=True, exist_ok=True)

# 2. Load and Normalize the Master Game Index
INDEX_URL = "https://raw.githubusercontent.com/gabriel1200/shot_data/refs/heads/master/game_dates.csv"
print(f"Fetching master game index from {INDEX_URL}...")
mapping_df = pd.read_csv(INDEX_URL, low_memory=False)

mapping_df['GAME_ID'] = pd.to_numeric(mapping_df['GAME_ID'], errors='coerce').fillna(0).astype(int)
mapping_df['TEAM_ID'] = pd.to_numeric(mapping_df['TEAM_ID'], errors='coerce').fillna(0).astype(int)

# Create a season lookup mapping: year integer (e.g. 2026) -> season string (e.g. "2025-26")
season_year_map = {}
for season_str in mapping_df['season'].dropna().unique():
    # '2025-26' -> 2026
    start_yr = int(season_str.split('-')[0])
    season_year_map[start_yr + 1] = season_str

# 3. Determine Target Years to Sync
cli_args = sys.argv[1:]

if '--all' in cli_args:
    # Discover all available all_*.parquet or all_*.csv in source_dir
    discovered_years = set()
    for f in source_dir.glob("all_*.parquet"):
        match = re.search(r'all_(\d{4})', f.stem)
        if match:
            discovered_years.add(int(match.group(1)))
    for f in source_dir.glob("all_*.csv"):
        match = re.search(r'all_(\d{4})', f.stem)
        if match:
            discovered_years.add(int(match.group(1)))
    target_years = sorted(list(discovered_years))
    print(f"Auto-discovered years to sync: {target_years}")

elif cli_args:
    # Parse explicit years passed as CLI arguments (e.g. python sync_career_logs.py 2024 2025 2026)
    target_years = sorted([int(y) for y in cli_args if y.isdigit()])
    print(f"Targeting specified years: {target_years}")

else:
    # Default fallback: Sync only the latest active season
    latest_season_str = mapping_df['season'].max()
    latest_year = int(latest_season_str.split('-')[0]) + 1
    target_years = [latest_year]
    print(f"No arguments passed. Defaulting to latest season: {latest_season_str} (Year: {latest_year})")

if not target_years:
    print("[!] No valid target years identified. Exiting.")
    sys.exit(0)

# 4. Processing Loop
for year in target_years:
    season_str = season_year_map.get(year, f"{year-1}-{str(year)[-2:]}")
    print(f"\n=======================================================")
    print(f" Syncing Season: {season_str} (Year {year})")
    print(f"=======================================================")

    # Check for both Regular Season and Playoffs files
    for is_ps in [False, True]:
        trail = 'ps' if is_ps else ''
        file_stem = f"all_{year}{trail}"
        parquet_file = source_dir / f"{file_stem}.parquet"
        csv_file = source_dir / f"{file_stem}.csv"

        if parquet_file.exists():
            print(f"--> Reading Parquet: {parquet_file.name}")
            df = pd.read_parquet(parquet_file)
        elif csv_file.exists():
            print(f"--> Reading CSV: {csv_file.name}")
            df = pd.read_csv(csv_file, low_memory=False)
        else:
            print(f"[-] Skipped: No file found for {file_stem} (.parquet or .csv)")
            continue

        # Normalize IDs
        df['GAME_ID'] = pd.to_numeric(df['GAME_ID'], errors='coerce').fillna(0).astype(int)
        df['TEAM_ID'] = pd.to_numeric(df['TEAM_ID'], errors='coerce').fillna(0).astype(int)
        df['PLAYER_ID'] = pd.to_numeric(df['PLAYER_ID'], errors='coerce').fillna(0).astype(int)
        df = df[df['PLAYER_ID'] != 0]

        # Merge with master game dates index to ensure consistent metadata
        cols_to_sync = ['HTM', 'VTM', 'opp_team', 'team', 'date', 'season', 'playoffs']
        df = df.drop(columns=[c for c in cols_to_sync if c in df.columns], errors='ignore')
        df = df.merge(mapping_df, on=['GAME_ID', 'TEAM_ID'], how='left')

        # Overwrite player career log files
        player_groups = df.groupby('PLAYER_ID')
        print(f"Updating career logs for {len(player_groups)} players ({'Playoffs' if is_ps else 'Regular Season'})...")

        for p_id, p_group in player_groups:
            player_file = target_dir / f"{int(p_id)}.csv"
            ps_flag = p_group['playoffs'].iloc[0]

            if player_file.exists():
                existing_df = pd.read_csv(player_file, low_memory=False)

                # Isolate and replace only the partition matching the current season and playoff state
                mask = (existing_df['season'] == season_str) & (existing_df['playoffs'] == ps_flag)
                existing_df = existing_df[~mask]

                combined_df = pd.concat([existing_df, p_group], ignore_index=True, sort=False)
                combined_df.to_csv(player_file, index=False)
            else:
                p_group.to_csv(player_file, index=False)

print("\n[✓] All targeted season career logs are successfully synchronized!")