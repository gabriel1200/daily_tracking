# clean_index.py
import pandas as pd

INDEX_FILE = "column_index.csv"

# Load current index
df = pd.read_csv(INDEX_FILE)

# 1. Clean whitespace across column names
df['col'] = df['col'].str.strip()

# 2. Filter out zero-variance metrics, leaks, and deprecated duplicates
bad_columns = {
    'overall_def_FREQ',   # Constant 1.0 for all players
    'D_FGA', 
    'D_FGM', 
    'D_FG_PCT', 
    'NORMAL_FG_PCT', 
    'PCT_PLUSMINUS'
}
df_clean = df[~df['col'].isin(bad_columns)].copy()

# 3. Sort cleanly by category and column name
df_clean = df_clean.sort_values(by=['category', 'start_year', 'col']).reset_index(drop=True)

# 4. Save sanitized index
df_clean.to_csv(INDEX_FILE, index=False)

print(f"[✓] Successfully cleaned {INDEX_FILE}!")
print(f"    Purged: {len(df) - len(df_clean)} columns (including overall_def_FREQ)")
print(f"    Canonical count: {len(df_clean)} columns")