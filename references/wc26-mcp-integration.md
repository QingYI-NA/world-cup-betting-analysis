# WC26 MCP Server — Integration Reference

## What It Is

`wc26-mcp` is an npm package (v0.3.1) that runs as a local MCP stdio server. It bundles
pre-loaded World Cup 2026 data: 104 matches, 48 teams, 16 venues, historical matchups,
team profiles, betting odds, injuries, news, and more. No external API calls — all data
ships inside the package.

## Installation

```bash
npm install -g wc26-mcp
```

Verify:
```bash
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | wc26-mcp
```

## Hermes Configuration

Added to `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  wc26:
    command: wc26-mcp
    timeout: 30
```

After restart, tools appear as `mcp_wc26_get_matches`, `mcp_wc26_get_teams`, etc.

## Available Tools (14 of 18 most relevant)

| Tool | Use in betting analysis | Replaces |
|------|------------------------|----------|
| `get_matches` | Match schedule with venue + timezone | football-data.org (but see limitations) |
| `get_teams` | All 48 teams with FIFA rankings, groups, confederations | `fifa_ranking.csv` |
| `get_team_profile` | Coach, key players, playing style, WC history | New data |
| `get_historical_matchups` | Full WC H2H history between any two teams | `h2h.csv` + API calculation |
| `compare_teams` | Side-by-side: rankings, odds, injuries, H2H in one call | Multiple lookups |
| `get_injuries` | Key player injury tracker (out/doubtful/recovering/fit) | `injuries.csv` |
| `get_odds` | Tournament winner, Golden Boot, group predictions | Supplement to The Odds API |
| `get_venues` | 16 venues: capacity, city, country, coordinates | New data |
| `get_standings` | Pre-tournament group power rankings | New data |
| `get_bracket` | Knockout bracket visualization | New data |
| `get_news` | ESPN/BBC/Reddit news, filterable by `category: injury` | New data |
| `what_to_know_now` | Zero-param: today's phase, upcoming matches, context | Quick briefing |
| `get_groups` | Group composition + match schedule per group | New data |
| `get_schedule` | Full tournament schedule organized by date | football-data.org |

## Critical Limitations

### 1. Schedule has placeholder team names ⚠️
The package was published Feb 2026, before all qualifiers were complete.
Team names like "UEFA Playoff A Winner" appear instead of actual qualified teams.
**Do NOT use for match schedule** — prefer football-data.org which has real team names.

### 2. Injuries may be sparse ⚠️
`get_injuries` returned 0 results for Canada in testing. The data is pre-loaded,
not real-time. Treat as supplementary to manual `injuries.csv`.

### 3. No live results ⚠️
All data is static/pre-tournament. For live scores, use football-data.org.

### 4. Team IDs are FIFA codes (lowercase 3-letter)
Examples: `can`, `usa`, `bra`, `arg`, `eng`, `fra`, `ger`, `esp`, `por`, `ned`.
Not football-data.org numeric IDs. Not full country names.

## Recommended Hybrid Strategy

```
Purpose                  → Source
─────────────────────────────────────────────
Match schedule (real)    → football-data.org API
Live scores/results      → football-data.org API (via WC finished matches)
Match odds (h2h)         → The Odds API (sport key: soccer_fifa_world_cup)
FIFA rankings            → MCP get_teams (primary, 48 teams) → CSV fallback
Injuries                 → MCP get_injuries (primary, 18 players / 15 teams) → CSV fallback
Recent form              → WC finished matches auto-calc (football-data.org)
Historical H2H           → WC finished matches auto-search (football-data.org)
Venues                   → MCP get_venues
Tournament context       → MCP what_to_know_now
```

**Result**: 100% automated when APIs + MCP are available. CSV templates exist only as offline fallbacks.

## Team Name Mapping (MCP ↔ football-data.org)

MCP uses FIFA codes. To convert football-data.org team names to MCP codes,
search `get_teams` output by name substring. The `_CHINESE_NAME_MAP` in
`fetch_data.py` already maps Chinese→English; FIFA codes can be added as
an additional column if needed.
