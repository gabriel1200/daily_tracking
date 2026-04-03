import pandas as pd
import glob
import os
from pathlib import Path

# 1. Setup paths relative to ~/basketball/daily_tracking
source_dir = Path("../player_sheets/game_report/all_games").resolve()
output_file = Path("column_index.csv")

csv_files = sorted(glob.glob(str(source_dir / "all_*.csv")))

if not csv_files:
    print(f"Error: No CSV files found in {source_dir}")
    exit()

column_stats = []

print(f"Analyzing schema across {len(csv_files)} files...")

for file_path in csv_files:
    file_name = os.path.basename(file_path)
    if any(x in file_name for x in ["sample", "master", "index"]):
        continue
    
    year_str = file_name.replace('all_', '').replace('ps.csv', '').replace('.csv', '')
    try:
        year = int(year_str)
    except ValueError:
        continue
        
    df = pd.read_csv(file_path, low_memory=False)
    total_rows = len(df)
    if total_rows == 0: continue

    for col in df.columns:
        non_null_count = df[col].notnull().sum()
        column_stats.append({
            'column_name': col,
            'year': year,
            'completeness': non_null_count / total_rows,
            'has_data': non_null_count > 0
        })

# 2. Process Results
full_stats = pd.DataFrame(column_stats)
index_df = full_stats.groupby('column_name').apply(lambda x: pd.Series({
    'start_year': x.loc[x['has_data'], 'year'].min() if x['has_data'].any() else None,
    'latest_year': x.loc[x['has_data'], 'year'].max() if x['has_data'].any() else None,
    'avg_completeness': x['completeness'].mean(),
    'consistency_score': x['has_data'].mean()
}), include_groups=False).reset_index()

index_df = index_df.dropna(subset=['start_year'])
index_df[['start_year', 'latest_year']] = index_df[['start_year', 'latest_year']].astype(int)

# 3. Refined Categorization Logic
def get_category(col):
    c = col.lower()
    
    # Tracking - Hustle (Effort plays)
    if any(x in c for x in ['hustle_', 'defle', 'contested_', 'charges_', 'screen_ast', 'boxout', 'box_out', 'loose_ball']):
        return 'Tracking - Hustle'
    
    # Tracking - Action/Possession (Ball movement & Player actions)
    if any(x in c for x in ['drive_', 'pass', 'potential_', 'touch', 'pull_up', 'catch_shoot', 'post_touch', 'elbow_touch', 'paint_touch']):
        return 'Tracking - Action'
    
    # Tracking - Movement (Physicality & Speed)
    if any(x in c for x in ['dist_', 'speed_', 'avg_sec', 'avg_drib']):
        return 'Tracking - Movement'
    
    # Advanced / Calculated Metrics
    if any(x in c for x in ['_pct', '_ratio', 'rating', 'pie', 'poss', 'pace', 'plus_minus', 'fantasy_pts']):
        # Filter out standard FG/FT/3P percentages to keep them in Box Score
        if not any(x in c for x in ['fg', 'ft', 'fg3']):
            return 'Advanced/Efficiency'
    
    # Rankings
    if '_rank' in c:
        return 'NBA.com Rankings'
    
    # Standard Box Score (The "Old School" stats)
    if any(x in c for x in ['pts', 'ast', 'reb', 'stl', 'blk', 'tov', 'pf', 'min', 'fgm', 'fga', 'ftm', 'fta', 'fg3m', 'fg3a']):
        return 'Standard Box Score'
    
    # Metadata & Identifiers
    if any(x in c for x in ['id', 'name', 'team', 'date', 'season', 'playoffs', 'htm', 'vtm']):
        return 'Metadata/Context'
    
    return 'Other'

index_df['category'] = index_df['column_name'].apply(get_category)

# 4. Final Formatting
index_df = index_df.sort_values(['start_year', 'category', 'column_name'])
index_df.to_csv(output_file, index=False)

print(f"Index created with {len(index_df)} active columns. Saved to: {output_file}")