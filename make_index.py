import time
import os
import pandas as pd
from nba_api.stats.endpoints import ShotChartDetail
from nba_api.stats.static import teams

# ---------------------------------------------------------
# 1. Apply your custom NBA API Headers / Patch
# ---------------------------------------------------------
NBA_STATS_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Host": "stats.nba.com",
    "Origin": "https://www.nba.com",
    "Pragma": "no-cache",
    "Referer": "https://www.nba.com/",
    "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
}

try:
    from nba_api.stats.library import http as stats_http
    from nba_api.library import http as base_http

    stats_http.STATS_HEADERS = NBA_STATS_HEADERS
    stats_http.NBAStatsHTTP.headers = NBA_STATS_HEADERS

    stats_http.NBAStatsHTTP._session = None
    base_http.NBAHTTP._session = None
except Exception as e:
    print(f"Warning: Could not patch nba_api headers: {e}")

# ---------------------------------------------------------
# 2. Setup Scraper Parameters
# ---------------------------------------------------------
WNBA_LEAGUE_ID = "10"
# Toggle this to 'Playoffs' when you are ready to pull the postseason data
CURRENT_SEASON_TYPE = "Regular Season" 

# Get all WNBA Teams
try:
    wnba_teams = teams.get_wnba_teams()
except AttributeError:
    all_teams = teams.get_teams()
    wnba_teams = [t for t in all_teams if str(t['id']).startswith('161166')]

start_year = 1997
end_year = 2023
seasons = [f"{year}-{str(year+1)[-2:]}" for year in range(start_year, end_year + 1)]

# ---------------------------------------------------------
# 3. Main Scraping Loop
# ---------------------------------------------------------
def scrape_wnba_team_shotcharts(teams_list, seasons_list, season_type="Regular Season"):
    
    print(f"Found {len(teams_list)} WNBA franchises. Beginning {season_type} scrape...")
    
    # Determine the folder suffix
    is_playoffs = (season_type == "Playoffs")
    folder_suffix = "ps" if is_playoffs else ""
    
    for season in seasons_list:
        print(f"\n--- Scraping Season: {season} ({season_type}) ---")
        
        # Extract base year and append 'ps' if it's the playoffs
        base_year = season.split('-')[0]
        folder_name = f"{base_year}{folder_suffix}"
        
        # Target directory: team/{year} or team/{year}ps
        target_dir = os.path.join("team", folder_name)
        os.makedirs(target_dir, exist_ok=True)
        
        for team in teams_list:
            team_id = team['id']
            team_name = team['full_name']
            
            try:
                # player_id=0 fetches all players for the specified team
                sc = ShotChartDetail(
                    team_id=team_id,
                    player_id=0,
                    context_measure_simple='FGA',
                    season_nullable=season,
                    season_type_all_star=season_type,
                    league_id=WNBA_LEAGUE_ID
                )
                
                # Index 0 is Shot_Chart_Detail
                team_shots_df = sc.get_data_frames()[0] 
                
                if not team_shots_df.empty:
                    team_shots_df['SEASON'] = season 
                    
                    # Save individual team CSV in the structured folder
                    file_path = os.path.join(target_dir, f"{team_id}.csv")
                    team_shots_df.to_csv(file_path, index=False)
                    
                    print(f"  [SUCCESS] {team_name}: Saved {len(team_shots_df)} shots to {file_path}")
                else:
                    print(f"  [EMPTY] {team_name} had no data for {season}.")
                    
            except Exception as e:
                print(f"  [ERROR] Failed to fetch {team_name} for {season}: {e}")
            
            # Critical: Sleep to prevent IP blocking/timeouts
            time.sleep(.5) 

    print(f"\n{season_type} scrape sequence complete!")

# Execute the scraper
if __name__ == "__main__":
    scrape_wnba_team_shotcharts(wnba_teams, seasons, season_type=CURRENT_SEASON_TYPE)