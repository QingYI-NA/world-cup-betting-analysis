---
name: world-cup-betting-analysis
description: >
  World Cup football betting analysis tool. Six-dimension scoring model
  (team strength, recent form, injuries, head-to-head, external factors,
  odds market) with probability calculation, risk rating, and tiered
  betting proposals. Fully automated data collection via The Odds API,
  Football-Data.org API, and WC26 MCP server. Zero manual CSV maintenance
  required. Outputs console report + JSON/CSV persistence. Use when the
  user wants to run match analysis, check today's matches, or generate
  betting proposals.
---

# World Cup Betting Analysis Tool

## Overview

Multi-layer pipeline: schedule → data collection → cleaning/scoring → analysis → proposals → output.

## Quick Start

```bash
cd ~/AppData/Local/hermes/skills/world-cup-betting-analysis/scripts
python main.py                    # Analyze all matches for today
python main.py --match "法国-阿根廷"  # Analyze specific match
python main.py --date 2026-06-15  # Analyze matches on a specific date
python main.py --verbose          # Detailed output
```

## Prerequisites

```bash
pip install requests
```

API keys are loaded from three sources (in priority order):
1. **System environment variables** — `FOOTBALL_DATA_API_KEY`, `ODDS_API_KEY`
2. **`.env` file** — place in the skill root directory (see `.env` template)
3. **Manual CSV fallback** — works without any API keys

`.env` file format:
```
FOOTBALL_DATA_API_KEY=your_token_here
ODDS_API_KEY=your_token_here
```

`config.py` loads `.env` automatically at import time — no extra setup needed.
Environment variables take precedence over `.env` values.

## File Structure

```
.env              # API keys (loaded automatically by config.py)
scripts/
  config.py       # All weights, thresholds, scoring tables, .env loader
  fetch_data.py   # Multi-source data collection with fallback
  analyze.py      # Six-dimension scoring + probability engine
  output.py       # Console display + JSON/CSV persistence
  main.py         # Orchestrator entry point (includes PYTHONHOME fix)

templates/
  injuries.csv     # Manual injury tracking
  fifa_ranking.csv # Manual FIFA rankings (TOP10 pre-filled)
  schedule.csv     # Manual schedule (API fallback)
  odds.csv         # Manual odds (API fallback)
  h2h.csv          # Historical head-to-head records
  recent_form.csv  # Recent form (last 5 matches points)

references/
  MAINTENANCE.md                 # Manual data maintenance guide
  football-data-api-patterns.md  # API integration patterns & free-tier limits
  python-env-troubleshooting.md  # Windows PYTHONHOME conflicts
  wc26-mcp-integration.md        # WC26 MCP server: tools, limits, hybrid strategy
```

## Data Flow

1. `main.py` loads schedule (Football-Data.org API → cache → `schedule.csv`)
2. `fetch_data.py` collects data with **automation-first** strategy:
   - **Odds**: The Odds API (`soccer_fifa_world_cup`) → cache → `odds.csv`
   - **FIFA rankings**: MCP `get_teams` → `fifa_ranking.csv` fallback
   - **Injuries**: MCP `get_injuries` (18 players, 15 teams) → `injuries.csv` fallback
   - **Recent form**: WC finished matches auto-calc → `recent_form.csv` fallback → default
   - **H2H**: WC finished matches auto-search → `h2h.csv` fallback → skip
   - **Team profiles / context**: MCP `get_team_profile`, `compare_teams`, `what_to_know_now`
3. `analyze.py` scores 6 dimensions, computes weighted totals
4. `analyze.py` converts scores → probabilities → risk rating → three-tier proposals
5. `output.py` generates console report (Beijing time, 🥉🥈🥇 tiers), saves JSON/CSV
6. Post-match: manually update `data/review/results.csv` for backtesting

**Automation coverage**: 100% of weighted dimensions when MCP is active.
Zero manual CSV maintenance required — even injuries and FIFA rankings come from MCP.
CSV templates exist only as offline fallbacks.

**Three-tier output format**: Every match shows 🥉 小额 / 🥈 稳健 / 🥇 博高赔
proposals with CNY amounts. Times are always Beijing (UTC+8).

## Daily Maintenance

**Zero manual steps required.** All data sources are automated:

| Data | Source | Manual needed? |
|------|--------|----------------|
| Schedule | Football-Data.org API | No |
| Odds | The Odds API | No |
| FIFA rankings | WC26 MCP `get_teams` | No |
| Injuries | WC26 MCP `get_injuries` | No |
| Recent form | WC finished matches | No |
| H2H | WC finished matches | No |

CSV templates under `templates/` serve as offline fallbacks only — populate them
if the APIs or MCP become unavailable.

## Cron Job

Cron job ID: `711c431d7878`
Schedule: daily at 17:00 Asia/Shanghai
Delivery: Feishu DM (oc_294ad292bc5583954460b62ab9579bc4)
Toolsets: terminal + web
Skills loaded: world-cup-betting-analysis

Each run loads this skill, executes `python main.py --compact`,
and sends the compact report to Feishu. On days with no matches,
sends "今日无世界杯比赛".

## Pitfalls

- **Wrong Odds API sport key**: The correct key is `soccer_fifa_world_cup`, NOT `soccer_world_cup`. Always discover via `GET /v4/sports` first.
- **Team name mismatch across APIs**: Football-Data.org uses "Czechia", Odds API uses "Czech Republic". Same for "Bosnia-Herzegovina" vs "Bosnia & Herzegovina". `fetch_data.py` has a `_NAME_NORMALIZE` mapping — extend it when new mismatches appear.
- **Football-Data.org free tier**: `GET /v4/teams/{id}/matches` returns 0 for national teams. Workaround: batch-fetch all WC results via `GET /v4/competitions/WC/matches?status=FINISHED`, then filter in-memory. One call feeds both recent-form and H2H.
- **Windows PYTHONHOME conflict**: If Python crashes with "SRE module mismatch", check `PYTHONHOME` env var. `main.py` auto-clears uv-induced conflicts. Permanent fix: delete `PYTHONHOME` from Windows system env vars.
- **WC26 MCP schedule has placeholder names**: Package from Feb 2026 uses "UEFA Playoff A Winner" etc. Use football-data.org for real team names in schedule. MCP is reliable for team profiles, FIFA rankings, H2H history, venues.
- **WC26 MCP injuries may be empty**: Pre-loaded data (18 players across 15 teams). For marquee teams (France, Argentina, Brazil, etc.) injury data is available; for smaller teams it returns empty. Falls back to `injuries.csv` or neutral defaults.
- **MCP subprocess on Windows**: `subprocess.run(['wc26-mcp'])` fails with `FileNotFoundError` — must use `['wc26-mcp.cmd']`. The `.cmd` extension is required for npm global packages on Windows when invoked via Python `subprocess`. The skill's `_MCP_CMD` already accounts for this.
- **Timezone**: All API times are UTC. `output.py` converts to Beijing time (UTC+8) via `_utc_to_beijing()`. Always display Beijing time.
- **Three-tier proposals**: Every match output must show 🥉 小额 / 🥈 稳健 / 🥇 博高赔. Generated by `_generate_all_tiers()` in `output.py`.
- **Probability normalization**: Done AFTER all adjustments (knockout boost, boundary protection) to guarantee sum = 1.0.
- **Missing data fallback**: Any missing dimension gets a neutral 5/10 score; match is flagged.
- **sports-skills**: `get_missing_players` is Premier League only. ESPN backend times out (30s+) for World Cup. Not usable.
- All monetary amounts in CNY.
