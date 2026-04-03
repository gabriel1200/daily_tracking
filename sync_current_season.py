import pandas as pd
import glob
import os
from pathlib import Path

# 1. Setup paths relative to ~/basketball/daily_tracking
source_dir = Path("../player_sheets/game_report/all_games").resolve()
target_dir = Path("careerlogs").resolve()
target_dir.mkdir(parents=True, exist_ok=True)

# 2. Load and Normalize the Master Game Index
INDEX_URL = "https://raw.githubusercontent.com/gabriel1200/shot_data/refs/heads/master/game_dates.csv"
print("Determining current season from master index...")
mapping_df = pd.read_csv(INDEX_URL)

# Normalize Index IDs
mapping_df['GAME_ID'] = pd.to_numeric(mapping_df['GAME_ID'], errors='coerce').fillna(0).astype(int)
mapping_df['TEAM_ID'] = pd.to_numeric(mapping_df['TEAM_ID'], errors='coerce').fillna(0).astype(int)

# 3. Determine the Current Season (NBA Syntax)
# Find the latest season string (e.g., "2025-26")
latest_season_str = mapping_df['season'].max()

# NBA Repo Syntax: 2025-26 is saved as 2026.csv
# We take the last 2 digits of the season string and append to the first 2 digits of the year
current_repo_year = latest_season_str[:2] + latest_season_str[-2:]

print(f"Latest season detected: {latest_season_str}")
print(f"Targeting repo year: {current_repo_year}")

# 4. Identify the files to process
target_patterns = [f"all_{current_repo_year}.csv", f"all_{current_repo_year}ps.csv"]
target_files = [source_dir / p for p in target_patterns if (source_dir / p).exists()]

if not target_files:
    print(f"Warning: No 'all_{current_repo_year}' files found in {source_dir}.")
    exit()

for file_path in target_files:
    file_name = os.path.basename(file_path)
    print(f"\nProcessing: {file_name}")
    
    # Load and Normalize
    df = pd.read_csv(file_path, low_memory=False)
    df['GAME_ID'] = pd.to_numeric(df['GAME_ID'], errors='coerce').fillna(0).astype(int)
    df['TEAM_ID'] = pd.to_numeric(df['TEAM_ID'], errors='coerce').fillna(0).astype(int)
    df['PLAYER_ID'] = pd.to_numeric(df['PLAYER_ID'], errors='coerce').fillna(0).astype(int)
    df = df[df['PLAYER_ID'] != 0]

    # Merge with index to fill metadata
    cols_to_sync = ['HTM', 'VTM', 'opp_team', 'team', 'date', 'season', 'playoffs']
    df = df.drop(columns=[c for c in cols_to_sync if c in df.columns])
    df = df.merge(mapping_df, on=['GAME_ID', 'TEAM_ID'], how='left')

    # 5. Overwrite and Save
    for p_id, p_group in df.groupby('PLAYER_ID'):
        player_file = target_dir / f"{int(p_id)}.csv"
        
        if player_file.exists():
            existing_df = pd.read_csv(player_file, low_memory=False)
            
            # Match on season string AND playoff status to avoid cross-pollination
            mask = (existing_df['season'] == latest_season_str) & \
                   (existing_df['playoffs'] == p_group['playoffs'].iloc[0])
            
            existing_df = existing_df[~mask]
            combined_df = pd.concat([existing_df, p_group], ignore_index=True, sort=False)
            combined_df.to_csv(player_file, index=False)
        else:
            p_group.to_csv(player_file, index=False)

print(f"\nSync complete. {latest_season_str} data is now live in career logs.")