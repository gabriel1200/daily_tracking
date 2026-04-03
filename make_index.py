import pandas as pd
import glob
import os
import requests
from pathlib import Path

# ==========================================
# 1. SETUP & PATHS
# ==========================================
# Current Dir: ~/basketball/daily_tracking
# Data Dir:    ~/basketball/player_sheets/game_report/all_games
BASE_DIR = Path(".").resolve()
SOURCE_DIR = (BASE_DIR.parent / "player_sheets" / "game_report" / "all_games").resolve()
LOGS_DIR = (BASE_DIR / "careerlogs").resolve()
INDEX_FILE = BASE_DIR / "column_index.csv"

# Master Game Index URL (Source of Truth for Metadata)
INDEX_URL = "https://raw.githubusercontent.com/gabriel1200/shot_data/refs/heads/master/game_dates.csv"

# Ensure directories exist
LOGS_DIR.mkdir(parents=True, exist_ok=True)

def get_mapping_df():
    """Downloads and normalizes the master game mapping file."""
    print(f"Downloading game index from GitHub...")
    df = pd.read_csv(INDEX_URL)
    # Normalize IDs to handle leading 00s (String -> Int conversion)
    df['GAME_ID'] = pd.to_numeric(df['GAME_ID'], errors='coerce').fillna(0).astype(int)
    df['TEAM_ID'] = pd.to_numeric(df['TEAM_ID'], errors='coerce').fillna(0).astype(int)
    return df

# ==========================================
# 2. CATEGORIZATION LOGIC (Scraper-Informed)
# ==========================================
def get_category_from_scraper(col):
    """Categorizes columns based on the specific prefixes used in game_report_scrape.py"""
    c = col.lower()
    
    # Defensive Tracking (Scraper url18-url23)
    if 'overall_def_' in c: return 'Defensive Tracking - Overall'
    if 'three_pt_def_' in c: return 'Defensive Tracking - 3PT'
    if 'two_pt_def_' in c: return 'Defensive Tracking - 2PT'
    if 'less_6ft_def_' in c: return 'Defensive Tracking - Rim (<6ft)'
    if 'less_10ft_def_' in c: return 'Defensive Tracking - Paint (<10ft)'
    if 'more_15ft_def_' in c: return 'Defensive Tracking - Perimeter (>15ft)'
    
    # Shot Context / Defenders (Scraper url7-url10)
    if 'very_tight_' in c: return 'Shot Context - Very Tight (0-2ft)'
    if 'tight_' in c: return 'Shot Context - Tight (2-4ft)'
    if 'open_' in c: return 'Shot Context - Open (4-6ft)'
    if 'wide_open_' in c: return 'Shot Context - Wide Open (6ft+)'
    
    # Play Types & Touches (Scraper url11-url13, url25)
    if 'pullup_' in c: return 'Play Type - Pull Up'
    if 'post_touch_' in c: return 'Play Type - Post Touch'
    if 'catch_shoot' in c: return 'Play Type - Catch and Shoot'
    if 'drive_' in c: return 'Play Type - Drives'
    
    # Hustle & Effort (Scraper url24)
    if 'hustle_' in c or any(x in c for x in ['boxout', 'box_out', 'screen_ast', 'defle', 'loose_ball', 'charges_drawn']):
        return 'Tracking - Hustle'
    
    # Movement & Passing
    if any(x in c for x in ['speed_distance_', 'dist_miles', 'avg_speed', 'touches', 'front_ct_touches', 'time_of_poss']):
        return 'Tracking - Physical/Touches'
    if any(x in c for x in ['pass_', 'potential_ast', 'ast_pts_created', 'ast_adj', 'secondary_ast']):
        return 'Tracking - Playmaking'

    # Efficiency & Ratings
    if any(x in c for x in ['pie', 'off_rating', 'def_rating', 'net_rating', 'ast_ratio', 'usg_pct', 'pace', 'ts_pct', 'efg_pct']):
        if '_rank' not in c: return 'Advanced - Efficiency'
            
    if '_rank' in c: return 'NBA.com Rankings'

    # Core Stats
    if any(x in c for x in ['pts', 'ast', 'reb', 'stl', 'blk', 'tov', 'pf', 'min', 'fgm', 'fga', 'ftm', 'fta', 'fg3m', 'fg3a']):
        return 'Standard Box Score'

    # Contextual info
    if any(x in c for x in ['player_id', 'team_id', 'game_id', 'date', 'year', 'season', 'playoffs', 'htm', 'vtm', 'opp_team']):
        return 'Metadata/Context'

    return 'Other/Uncategorized'

# ==========================================
# 3. CORE PROCESSING FUNCTIONS
# ==========================================

def run_full_generation():
    """Iterates through all yearly files and builds career logs from scratch."""
    mapping_df = get_mapping_df()
    csv_files = sorted(glob.glob(str(SOURCE_DIR / "all_*.csv")))
    
    for file_path in csv_files:
        file_name = os.path.basename(file_path)
        if any(x in file_name for x in ["sample", "master"]): continue
        
        print(f"Generating from: {file_name}")
        df = pd.read_csv(file_path, low_memory=False)
        
        # Normalize IDs
        df['GAME_ID'] = pd.to_numeric(df['GAME_ID'], errors='coerce').fillna(0).astype(int)
        df['TEAM_ID'] = pd.to_numeric(df['TEAM_ID'], errors='coerce').fillna(0).astype(int)
        
        # Inject Metadata from Index
        cols_to_replace = ['HTM', 'VTM', 'opp_team', 'team', 'date', 'season', 'playoffs']
        df = df.drop(columns=[c for c in cols_to_replace if c in df.columns], errors='ignore')
        df = df.merge(mapping_df, on=['GAME_ID', 'TEAM_ID'], how='left')
        
        df['PLAYER_ID'] = pd.to_numeric(df['PLAYER_ID'], errors='coerce').fillna(0).astype(int)
        df = df[df['PLAYER_ID'] != 0]

        for p_id, p_group in df.groupby('PLAYER_ID'):
            player_file = LOGS_DIR / f"{int(p_id)}.csv"
            if player_file.exists():
                existing = pd.read_csv(player_file, low_memory=False)
                pd.concat([existing, p_group], ignore_index=True, sort=False).to_csv(player_file, index=False)
            else:
                p_group.to_csv(player_file, index=False)

def sync_latest_season():
    """Determines the current active season from mapping and updates career logs (Overwrite Mode)."""
    mapping_df = get_mapping_df()
    latest_season_str = mapping_df['season'].max()
    
    # NBA Syntax: 2025-26 -> 2026.csv
    repo_year = latest_season_str[:2] + latest_season_str[-2:]
    print(f"Syncing Current Season: {latest_season_str} (Repo Year: {repo_year})")
    
    target_files = [SOURCE_DIR / f"all_{repo_year}.csv", SOURCE_DIR / f"all_{repo_year}ps.csv"]
    
    for file_path in target_files:
        if not file_path.exists(): continue
        
        df = pd.read_csv(file_path, low_memory=False)
        df['GAME_ID'] = pd.to_numeric(df['GAME_ID'], errors='coerce').fillna(0).astype(int)
        df['TEAM_ID'] = pd.to_numeric(df['TEAM_ID'], errors='coerce').fillna(0).astype(int)
        
        # Merge Metadata
        cols_to_replace = ['HTM', 'VTM', 'opp_team', 'team', 'date', 'season', 'playoffs']
        df = df.drop(columns=[c for c in cols_to_replace if c in df.columns], errors='ignore')
        df = df.merge(mapping_df, on=['GAME_ID', 'TEAM_ID'], how='left')
        
        df['PLAYER_ID'] = pd.to_numeric(df['PLAYER_ID'], errors='coerce').fillna(0).astype(int)
        
        for p_id, p_group in df[df['PLAYER_ID'] != 0].groupby('PLAYER_ID'):
            player_file = LOGS_DIR / f"{int(p_id)}.csv"
            if player_file.exists():
                existing = pd.read_csv(player_file, low_memory=False)
                # Remove old entries for this season/playoff combo to prevent duplicates
                mask = (existing['season'] == latest_season_str) & (existing['playoffs'] == p_group['playoffs'].iloc[0])
                existing = existing[~mask]
                pd.concat([existing, p_group], ignore_index=True, sort=False).to_csv(player_file, index=False)
            else:
                p_group.to_csv(player_file, index=False)

def generate_column_index():
    """Generates a schema map of start years and categories for all columns."""
    csv_files = sorted(glob.glob(str(SOURCE_DIR / "all_*.csv")))
    stats = []

    for file_path in csv_files:
        file_name = os.path.basename(file_path)
        if any(x in file_name for x in ["sample", "master"]): continue
        year = int(file_name.replace('all_', '').replace('ps.csv', '').replace('.csv', ''))
        
        df = pd.read_csv(file_path, low_memory=False)
        for col in df.columns:
            non_null = df[col].notnull().sum()
            stats.append({'col': col, 'year': year, 'comp': non_null / len(df) if len(df)>0 else 0, 'has': non_null > 0})

    df_stats = pd.DataFrame(stats)
    idx = df_stats.groupby('col').apply(lambda x: pd.Series({
        'start_year': x.loc[x['has'], 'year'].min() if x['has'].any() else None,
        'avg_completeness': x['comp'].mean(),
        'category': get_category_from_scraper(x.name)
    }), include_groups=False).reset_index().dropna(subset=['start_year'])
    
    idx['start_year'] = idx['start_year'].astype(int)
    idx.sort_values(['start_year', 'category', 'col']).to_csv(INDEX_FILE, index=False)
    print(f"Column index saved to {INDEX_FILE}")

# ==========================================
# 4. EXECUTION
# ==========================================
if __name__ == "__main__":
    import sys
    print("\nNBA Career Log Manager")
    print("1: Full Rebuild (Slow - processes all years)")
    print("2: Daily Sync (Fast - updates current season only)")
    print("3: Update Column Index")
    
    choice = input("\nSelect an option: ")
    
    if choice == '1': run_full_generation()
    elif choice == '2': sync_latest_season()
    elif choice == '3': generate_column_index()
    else: print("Invalid selection.")