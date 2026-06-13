# Football Data API Integration Patterns

Key lessons from building the automated data pipeline for World Cup betting analysis.

---

## 1. The Odds API — Sport Key Discovery

**Pitfall**: Guessing the sport key. `soccer_world_cup` is WRONG.

**Correct approach**: Always discover via `/sports` endpoint first.

```python
GET https://api.the-odds-api.com/v4/sports/?apiKey=YOUR_KEY
# Find: soccer_fifa_world_cup (active=True)
# Then: GET /v4/sports/soccer_fifa_world_cup/odds?apiKey=...&regions=eu&markets=h2h
```

The correct key for 2026 World Cup is **`soccer_fifa_world_cup`**, not `soccer_world_cup`.

## 2. Team Name Normalization Across APIs

Different APIs use different names for the same team. Must normalize before matching.

| Football-Data.org | The Odds API |
|---|---|
| Czechia | Czech Republic |
| Bosnia-Herzegovina | Bosnia & Herzegovina |
| USA | USA (both same) |
| South Korea | South Korea (both same) |
| Ivory Coast | Côte d'Ivoire |
| Cape Verde | Cabo Verde |
| DR Congo | Congo DR |
| Curaçao | Curaçao (both same) |

Implementation: `_normalize_name()` in `fetch_data.py` with a hardcoded mapping dict.

## 3. Football-Data.org Free Tier Limitation

**Problem**: `GET /v4/teams/{id}/matches` returns 0 results for national teams on the free tier. The team endpoint only returns club data.

**Workaround**: Use the competition endpoint instead.

```python
# DON'T: per-team query (free tier returns empty)
GET /v4/teams/773/matches?limit=5&status=FINISHED  # → 0 results

# DO: fetch all WC finished matches in one call
GET /v4/competitions/WC/matches?status=FINISHED&limit=100
# → all completed World Cup matches with scores
```

This single call feeds BOTH the recent-form calculator and the H2H finder. Cache the response for 1 hour to avoid hitting rate limits.

## 4. Rate Limits

- Football-Data.org free tier: 10 requests/minute
- The Odds API free tier: 500 requests/month (used to be 100)

The tool caches all API responses to `data/raw/*_cache.json` and reuses them within freshness windows.

## 5. Chinese ↔ English Team Name Mapping

The user's FIFA ranking CSV uses Chinese names (阿根廷, 西班牙). The API returns English. The `_CHINESE_NAME_MAP` in `fetch_data.py` maps all 48 World Cup teams both ways, and the CSV reader auto-detects the format (old `月份,球队,排名` vs new `rank,team`).

## 6. WC26 MCP as Supplementary Data Source

The `wc26-mcp` npm package provides pre-loaded 2026 World Cup data (teams, FIFA
rankings, historical matchups, team profiles, venues, injuries). Configured in
`~/.hermes/config.yaml` as an MCP server. Tools appear as `mcp_wc26_*`.

**Strengths**: FIFA rankings, team profiles, historical H2H, venue data.
**Weaknesses**: Schedule has placeholder names (package published Feb 2026).
Injuries may be empty (static data, not real-time).

Hybrid strategy: football-data.org for live schedule/scores, Odds API for
match odds, MCP for team/venue/profile enrichment.

See `references/wc26-mcp-integration.md` for full tool list and limitations.
