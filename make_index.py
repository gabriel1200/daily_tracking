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
    c = col.lower().strip()

    # ── 1. METADATA / CONTEXT ─────────────────────────────────────────────────
    if c in ('player_id','player_name','nickname','team_id','team_abbreviation',
             'team_abbr','player_last_team_abbreviation','player_position',
             'age','g','gp','w','l','w_pct','min','min1','team_count',
             'year','date','playoffs','game_id','index','htm','vtm',
             'opp_team_abbr','opp_team_id','opp_team_id ','player_last_team_id',
             'season','opp_team'):
        return 'Metadata/Context'

    # ── 2. PREFIXED BLOCKS (defensive tracking, shot context, hustle, post, sp_work) ──

    # Defensive tracking (url18-23)
    if c.startswith('overall_def_'):   return 'Defensive Tracking - Overall'
    if c.startswith('three_pt_def_'):  return 'Defensive Tracking - 3PT'
    if c.startswith('two_pt_def_'):    return 'Defensive Tracking - 2PT'
    if c.startswith('less_6ft_def_'):  return 'Defensive Tracking - Rim (<6ft)'
    if c.startswith('less_10ft_def_'): return 'Defensive Tracking - Paint (<10ft)'
    if c.startswith('more_15ft_def_'): return 'Defensive Tracking - Perimeter (>15ft)'

    # Shot-contest context (url7-10)
    if c.startswith('very_tight_'): return 'Shot Context - Very Tight (0-2ft)'
    if c.startswith('tight_'):      return 'Shot Context - Tight (2-4ft)'
    if c.startswith('open_'):       return 'Shot Context - Open (4-6ft)'
    if c.startswith('wide_open_'):  return 'Shot Context - Wide Open (6ft+)'

    # Hustle stats (url24)
    if c.startswith('hustle_'): return 'Tracking - Hustle'

    # Post touch (url25) — includes double-prefixed post_touch_POST_TOUCH_* columns
    if c.startswith('post_touch_'): return 'Play Type - Post Touch'

    # Estimated ratings from df12 efficiency endpoint
    if c.startswith('sp_work_'): return 'Advanced - Estimated Ratings (sp_work)'

    # ── 3. PLAY TYPES ─────────────────────────────────────────────────────────

    # Pull-up shots — scraper produces PULL_UP_ (df11, all-caps shotcolumns2)
    # NOTE: old code checked 'pullup_' which never matched real data
    if c.startswith('pull_up_') or c.startswith('pullup_'):
        return 'Play Type - Pull Up'

    # Catch & shoot (url16)
    if c.startswith('catch_shoot_'):
        return 'Play Type - Catch and Shoot'

    # Drives (url4) — raw columns are DRIVE_ (all-caps)
    if c.startswith('drive_') or c == 'drives':
        return 'Play Type - Drives'

    # ── 4. SHOT ZONES / LOCATIONS ─────────────────────────────────────────────

    # By-zone locations (url13 — RA, ITP, MID, corners, above-break, backcourt)
    if c in ('ra_fgm','ra_fga','ra_fg_pct',
             'itp_fgm','itp_fga','itp_fg_pct',
             'mid_fgm','mid_fga','mid_fg_pct',
             'left_corner_3_fgm','left_corner_3_fga','left_corner_3_fg_pct',
             'right_corner_3_fgm','right_corner_3_fga','right_corner_3_fg_pct',
             'corner_3_fgm','corner_3_fga','corner_3_fg_pct',
             'above_break_3_fgm','above_break_3_fga','above_break_3_fg_pct',
             'backcourt_fgm','backcourt_fga','backcourt_fg_pct'):
        return 'Shot Locations - By Zone'

    # 5-ft distance bands (url15 — FGM_LT_5 through FGM_40_PLUS)
    _dist_prefixes = ('fgm_lt_','fga_lt_','fgp_lt_',
                      'fgm_5_','fga_5_','fgp_5_',
                      'fgm_10_','fga_10_','fgp_10_',
                      'fgm_15_','fga_15_','fgp_15_',
                      'fgm_20_','fga_20_','fgp_20_',
                      'fgm_25_','fga_25_','fgp_25_',
                      'fgm_30_','fga_30_','fgp_30_',
                      'fgm_35_','fga_35_','fgp_35_',
                      'fgm_40_','fga_40_','fgp_40_')
    if any(c.startswith(p) for p in _dist_prefixes):
        return 'Shot Locations - 5ft Distance Bands'

    # Unprefixed df14 rim-defense columns (Overall <6ft defense, before prefix rename)
    if c in ('lt_06_pct','fgm_lt_06','fga_lt_06','ns_lt_06_pct',
             'freq','plusminus','pct_plusminus',
             'd_fga','d_fgm','d_fg_pct','normal_fg_pct'):
        return 'Defensive Tracking - Rim (<6ft)'

    # ── 5. REBOUNDING TRACKING (url6) ─────────────────────────────────────────
    _reb_terms = ('reb_chance','oreb_chance','dreb_chance',
                  'reb_contest','oreb_contest','dreb_contest',
                  'reb_uncontest','oreb_uncontest','dreb_uncontest',
                  'avg_oreb_dist','avg_dreb_dist','avg_reb_dist',
                  'reb_chance_defer','oreb_chance_defer','dreb_chance_defer')
    if any(x in c for x in _reb_terms):
        return 'Tracking - Rebounding Contests'

    # ── 6. SPEED / DISTANCE TRACKING (url26) ──────────────────────────────────
    if c in ('avg_speed','avg_speed_off','avg_speed_def',
             'dist_miles','dist_miles_off','dist_miles_def','dist_feet'):
        return 'Tracking - Speed & Distance'

    # ── 7. TOUCHES / POSSESSIONS (url5 + df12 touch efficiency) ──────────────
    _touch_terms = ('touches','time_of_poss','front_ct_touches',
                    'paint_touches','elbow_touches','post_touches',
                    'avg_drib_per_touch','avg_sec_per_touch',
                    'pts_per_touch','pts_per_paint_touch',
                    'pts_per_elbow_touch','pts_per_post_touch',
                    'paint_touch_fg_pct','paint_touch_pts',
                    'elbow_touch_fg_pct','elbow_touch_pts',
                    'post_touch_fg_pct','post_touch_pts',
                    'points')
    if any(x in c for x in _touch_terms):
        return 'Tracking - Physical/Touches'

    # ── 8. PASSING / PLAYMAKING (url3) ────────────────────────────────────────
    _pass_terms = ('passes_made','passes_received','potential_ast',
                   'ast_pts_created','ast_points_created',
                   'ast_adj','secondary_ast','ft_ast',
                   'ast_to_pass_pct','ast_to_pass_pct_adj')
    if any(x in c for x in _pass_terms) or c.startswith('pass_'):
        return 'Tracking - Playmaking'

    # ── 9. NBA.COM RANKINGS (always before generic suffix checks) ─────────────
    if c.endswith('_rank'):
        return 'NBA.com Rankings'

    # ── 10. ADVANCED / EFFICIENCY (url2 — Advanced MeasureType) ──────────────
    _adv_terms = ('pie','off_rating','def_rating','net_rating',
                  'e_off_rating','e_def_rating','e_net_rating',
                  'e_pace','e_tov_pct','e_usg_pct',
                  'ast_ratio','ast_pct','ast_to',
                  'usg_pct','pace','pace_per40',
                  'ts_pct','efg_pct','eff_fg_pct',
                  'tm_tov_pct','oreb_pct','dreb_pct','reb_pct',
                  'poss','team_poss')
    if any(x in c for x in _adv_terms):
        return 'Advanced - Efficiency'

    # ── 11. DERIVED / FANTASY ─────────────────────────────────────────────────
    if any(x in c for x in ('nba_fantasy_pts','wnba_fantasy_pts','dd2','td3',
                             'plus_minus','w_pct','fgm_pg','fga_pg')):
        return 'Derived / Fantasy'

    # ── 12. STANDARD BOX SCORE (url1 — Base MeasureType) ─────────────────────
    if any(x in c for x in ('pts','ast','reb','stl','blk','blka','tov','pf','pfd',
                             'fgm','fga','fg_pct','fg3m','fg3a','fg3_pct',
                             'ftm','fta','ft_pct','oreb','dreb')):
        return 'Standard Box Score'

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