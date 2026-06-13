"""
数据采集层：多源降级策略（v3 MCP 集成版）

自动化程度：
  ✅ 赛程     — Football-Data.org API → CSV 兜底
  ✅ 赔率     — The Odds API → CSV 兜底
  ✅ 近期状态 — WC 完赛场次自动计分 → CSV 兜底
  ✅ 历史交锋 — WC26 MCP → WC 赛事统计 → CSV 兜底
  ✅ 伤停     — WC26 MCP get_injuries → CSV 兜底
  ✅ FIFA排名 — WC26 MCP get_teams → CSV 兜底
"""

import json
import csv
import subprocess
import logging
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

try:
    import requests
except ImportError:
    requests = None

from config import (
    FOOTBALL_DATA_API_KEY, ODDS_API_KEY,
    TEMPLATES_DIR, RAW_DIR,
    DEFAULT_RECENT_POINTS, DEFAULT_INJURY_COUNT,
)

log = logging.getLogger("fetch_data")


# ============================================================
# WC26 MCP 客户端
# ============================================================

_MCP_CMD = "wc26-mcp.cmd"  # Windows: needs .cmd extension for subprocess
_MCP_AVAILABLE = None  # None=未检测, True/False=缓存结果


def _mcp_available():
    """检测 wc26-mcp 是否可用"""
    global _MCP_AVAILABLE
    if _MCP_AVAILABLE is not None:
        return _MCP_AVAILABLE
    try:
        subprocess.run([_MCP_CMD], timeout=5, capture_output=True)
        _MCP_AVAILABLE = True
    except Exception:
        _MCP_AVAILABLE = False
    return _MCP_AVAILABLE


def _mcp_call(tool_name, arguments=None, timeout=15):
    """
    调用 WC26 MCP 工具。
    返回解析后的 Python dict 或 None。
    """
    if not _mcp_available():
        return None
    req = json.dumps({
        "jsonrpc": "2.0", "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments or {}}
    })
    try:
        result = subprocess.run(
            [_MCP_CMD], input=req + "\n", capture_output=True,
            text=True, timeout=timeout)
        # MCP 服务器输出可能包含初始化协议消息，取最后一行有效 JSON
        for line in reversed(result.stdout.strip().split("\n")):
            try:
                r = json.loads(line)
                content = r.get("result", {}).get("content", [{}])[0].get("text", "{}")
                return json.loads(content)
            except (json.JSONDecodeError, KeyError, IndexError):
                continue
        return None
    except Exception as e:
        log.debug(f"MCP {tool_name}: {e}")
        return None


# ============================================================
# 缓存工具
# ============================================================

def _load_cache(name):
    path = RAW_DIR / f"{name}_cache.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _save_cache(name, data):
    path = RAW_DIR / f"{name}_cache.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


# ============================================================
# HTTP 工具
# ============================================================

def _fd_request(endpoint, params=None, timeout=15):
    """Football-Data.org API 通用请求"""
    if not FOOTBALL_DATA_API_KEY or not requests:
        return None
    url = f"https://api.football-data.org/v4/{endpoint}"
    try:
        resp = requests.get(url,
            headers={"X-Auth-Token": FOOTBALL_DATA_API_KEY},
            params=params or {}, timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        log.debug(f"FD API {endpoint}: {e}")
    return None


# ============================================================
# 1. 赛程
# ============================================================

def fetch_schedule(date_str=None):
    """今日赛程。API → 缓存 → CSV"""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    matches = []

    data = _fd_request("competitions/WC/matches",
                       {"dateFrom": date_str, "dateTo": date_str})
    if data:
        for m in data.get("matches", []):
            ht, at = m.get("homeTeam", {}), m.get("awayTeam", {})
            matches.append({
                "match_id": str(m.get("id", "")),
                "home": ht.get("name", "?"),
                "away": at.get("name", "?"),
                "kickoff": m.get("utcDate", ""),
                "stage": m.get("stage", "GROUP_STAGE"),
                "source": "api",
            })
        _save_cache("schedule", matches)
        return matches

    cached = _load_cache("schedule")
    if cached:
        filtered = [m for m in cached if date_str in m.get("kickoff", "")]
        if filtered:
            for m in filtered:
                m["source"] = "cache"
            return filtered

    csv_path = TEMPLATES_DIR / "schedule.csv"
    if csv_path.exists():
        with open(csv_path, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("日期", "") == date_str:
                    matches.append({
                        "match_id": row.get("比赛ID", f"{row['主队']}-{row['客队']}"),
                        "home": row["主队"], "away": row["客队"],
                        "kickoff": f"{row['日期']}T{row.get('开球时间', '18:00')}:00",
                        "stage": row.get("阶段", "小组赛"),
                        "source": "csv",
                    })
    return matches


# ============================================================
# 2. 赔率（全自动：Odds API）
# ============================================================

# 两个 API 之间的队名映射（Football-Data.org → Odds API）
_NAME_NORMALIZE = {
    "czechia": "czech republic",
    "bosnia-herzegovina": "bosnia & herzegovina",
    "united states": "usa",
    "ivory coast": "côte d'ivoire",
    "cape verde": "cabo verde",
    "dr congo": "congo dr",
    "curacao": "curaçao",
}


def _normalize_name(name):
    """标准化队名用于跨 API 匹配"""
    n = name.lower().strip()
    return _NAME_NORMALIZE.get(n, n)


def fetch_odds(home, away):
    """
    赔率。Odds API → 缓存 → CSV
    修复：使用正确的 sport key soccer_fifa_world_cup
    """
    if ODDS_API_KEY and requests:
        try:
            url = "https://api.the-odds-api.com/v4/sports/soccer_fifa_world_cup/odds"
            resp = requests.get(url,
                params={"apiKey": ODDS_API_KEY, "regions": "eu",
                        "markets": "h2h", "oddsFormat": "decimal"},
                timeout=10)
            if resp.status_code == 200:
                nh = _normalize_name(home)
                na = _normalize_name(away)
                for game in resp.json():
                    gh = _normalize_name(game.get("home_team", ""))
                    ga = _normalize_name(game.get("away_team", ""))
                    # 双向匹配（主客可能交换）
                    if (nh == gh and na == ga) or (nh == ga and na == gh):
                        for bm in game.get("bookmakers", []):
                            for mkt in bm.get("markets", []):
                                if mkt.get("key") == "h2h":
                                    outs = {o["name"]: o["price"] for o in mkt["outcomes"]}
                                    result = {
                                        "home": outs.get(game["home_team"], 2.5),
                                        "draw": outs.get("Draw", 3.2),
                                        "away": outs.get(game["away_team"], 2.8),
                                        "bookmaker": bm.get("key", ""),
                                        "source": "api",
                                    }
                                    _save_cache(f"odds_{home}_{away}", result)
                                    return result
        except Exception:
            pass

    cached = _load_cache(f"odds_{home}_{away}")
    if cached:
        cached["source"] = "cache_stale"
        return cached

    csv_path = TEMPLATES_DIR / "odds.csv"
    if csv_path.exists():
        with open(csv_path, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("主队", "") == home and row.get("客队", "") == away:
                    return {
                        "home": float(row.get("主胜赔率", 2.5)),
                        "draw": float(row.get("平局赔率", 3.2)),
                        "away": float(row.get("客胜赔率", 2.8)),
                        "source": "csv",
                    }
    return None


# ============================================================
# 3. FIFA 排名（MCP → CSV）
# ============================================================

_FIFA_CACHE = {}  # 球队名 → 排名


def _mcp_get_fifa_ranking(team_name):
    """从 WC26 MCP 获取 FIFA 排名"""
    if team_name in _FIFA_CACHE:
        return _FIFA_CACHE[team_name]

    # 先获取所有球队（缓存）
    if not _FIFA_CACHE:
        data = _mcp_call("get_teams")
        if data:
            teams = data.get("teams", [])
            for t in teams:
                name = t.get("name", "")
                rank = t.get("fifa_ranking")
                if name and rank:
                    _FIFA_CACHE[name.lower()] = rank
            log.info(f"MCP 球队缓存: {len(_FIFA_CACHE)} 支球队")

    return _FIFA_CACHE.get(team_name.lower())


def fetch_fifa_ranking(team_name):
    """
    获取 FIFA 排名。MCP → CSV（新旧格式兼容）
    """
    # 1) MCP
    rank = _mcp_get_fifa_ranking(team_name)
    if rank:
        return rank

    # 2) CSV 兜底
    csv_path = TEMPLATES_DIR / "fifa_ranking.csv"
    if not csv_path.exists():
        return None

    # 检测 CSV 格式
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []

    # 格式1: 月份,球队,排名
    # 格式2: rank,team (新格式)
    is_new_format = "rank" in fieldnames and "team" in fieldnames and "月份" not in fieldnames

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if is_new_format:
                csv_team = row.get("team", "").strip()
                csv_rank = int(row.get("rank", 0))
                # 直接匹配（CSV 兜底通常用英文名）
                if csv_team.lower() == team_name.lower():
                    return csv_rank
            else:
                if row.get("球队", "").strip() == team_name.strip():
                    return int(row.get("排名", 0))

    return None


# ============================================================
# 4. 伤停（MCP → CSV）
# ============================================================

_INJURY_CACHE = {}


def _mcp_get_injuries(team_name):
    """从 WC26 MCP 获取伤停信息"""
    team_lower = team_name.lower()
    if team_lower in _INJURY_CACHE:
        return _INJURY_CACHE[team_lower]

    data = _mcp_call("get_injuries")
    if not data:
        return None

    injuries = data.get("injuries", [])
    for inj in injuries:
        team = inj.get("team", "")
        clean_team = team.split(" ", 1)[-1] if " " in team else team
        tkey = clean_team.lower()
        _INJURY_CACHE.setdefault(tkey, []).append(inj)

    log.info(f"MCP 伤停缓存: {len(injuries)} 条, {len(_INJURY_CACHE)} 支球队")
    return _INJURY_CACHE.get(team_lower)


def fetch_injuries(home, away):
    """
    获取核心伤停。MCP → CSV → 默认值
    """
    default = {
        "home_count": DEFAULT_INJURY_COUNT,
        "away_count": DEFAULT_INJURY_COUNT,
        "home_names": "未知", "away_names": "未知",
        "source": "missing", "fresh": False,
    }

    # 1) MCP
    inj_h = _mcp_get_injuries(home)
    inj_a = _mcp_get_injuries(away)

    if inj_h is not None or inj_a is not None:
        hn_set = set()
        for i in (inj_h or []):
            if i.get("status") in ("out", "doubtful"):
                hn_set.add(i.get("player", "?"))
        an_set = set()
        for i in (inj_a or []):
            if i.get("status") in ("out", "doubtful"):
                an_set.add(i.get("player", "?"))
        hn_list = list(hn_set)
        an_list = list(an_set)
        return {
            "home_count": len(hn_list),
            "away_count": len(an_list),
            "home_names": "、".join(hn_list) if hn_list else "无",
            "away_names": "、".join(an_list) if an_list else "无",
            "source": "mcp",
            "fresh": True,
        }

    # 2) CSV 兜底
    csv_path = TEMPLATES_DIR / "injuries.csv"
    if not csv_path.exists():
        return default

    best, best_time = None, ""
    with open(csv_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("主队", "").strip() == home.strip() and row.get("客队", "").strip() == away.strip():
                t = row.get("更新时间", "")
                if t > best_time:
                    best_time = t
                    best = row
    if best is None:
        return default

    hn = best.get("主队缺阵核心", "").strip()
    an = best.get("客队缺阵核心", "").strip()
    hc = 0 if not hn or hn == "无" else len(hn.split("、"))
    ac = 0 if not an or an == "无" else len(an.split("、"))
    try:
        dt = datetime.fromisoformat(best_time)
        fresh = (datetime.now() - dt) < timedelta(hours=24)
    except Exception:
        fresh = False
    return {
        "home_count": hc, "away_count": ac,
        "home_names": hn if hn else "无",
        "away_names": an if an else "无",
        "source": "csv_fresh" if fresh else "csv_stale",
        "fresh": fresh,
    }


# ============================================================
# 5 & 6. 批量获取 WC 完赛数据（近期状态 + 历史交锋共用）
# ============================================================

_wc_finished_cache = None  # 内存缓存，一次运行只请求一次


def _fetch_all_finished_wc_matches():
    """
    一次性获取世界杯所有已完赛的比赛。
    返回: list[dict]，每场包含 home, away, home_score, away_score
    """
    global _wc_finished_cache
    if _wc_finished_cache is not None:
        return _wc_finished_cache

    # 先查缓存文件
    cached = _load_cache("wc_finished")
    cache_age = None
    if cached:
        try:
            # 检查缓存中最新比赛的时间
            latest = max(
                (m.get("utcDate", "") for m in cached if m.get("utcDate")),
                default="")
            if latest:
                cache_age = datetime.now() - datetime.fromisoformat(
                    latest.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            pass

    # 缓存未过期（1小时内，且当天有新比赛则强制刷新）
    if cached and cache_age and cache_age < timedelta(hours=1):
        _wc_finished_cache = cached
        return cached

    # API 请求
    data = _fd_request("competitions/WC/matches",
                       {"status": "FINISHED", "limit": 100})
    if data:
        matches = []
        for m in data.get("matches", []):
            score = m.get("score", {}).get("fullTime", {})
            h = score.get("home")
            a = score.get("away")
            if h is None or a is None:
                continue
            matches.append({
                "home": m["homeTeam"]["name"],
                "away": m["awayTeam"]["name"],
                "home_score": h,
                "away_score": a,
                "stage": m.get("stage", ""),
                "utcDate": m.get("utcDate", ""),
            })
        log.info(f"WC 完赛场次: {len(matches)} 场 (API)")
        _save_cache("wc_finished", matches)
        _wc_finished_cache = matches
        return matches

    # 兜底缓存
    if cached:
        _wc_finished_cache = cached
        return cached

    _wc_finished_cache = []
    return []


def _compute_recent_form_from_wc(team_name, max_matches=5):
    """
    从世界杯完赛数据中计算球队近 N 场积分。
    返回: (points: int, matches_used: int, source: str)
    """
    matches = _fetch_all_finished_wc_matches()
    if not matches:
        return None, 0, "no_data"

    # 该队参与的比赛（按时间倒序）
    team_matches = []
    for m in matches:
        if m["home"] == team_name or m["away"] == team_name:
            team_matches.append(m)

    if not team_matches:
        return None, 0, "no_match"

    # 取最近 N 场
    team_matches.sort(key=lambda x: x.get("utcDate", ""), reverse=True)
    recent = team_matches[:max_matches]

    points = 0
    for m in recent:
        if m["home"] == team_name:
            if m["home_score"] > m["away_score"]:
                points += 3
            elif m["home_score"] == m["away_score"]:
                points += 1
        else:
            if m["away_score"] > m["home_score"]:
                points += 3
            elif m["away_score"] == m["home_score"]:
                points += 1

    log.debug(f"  {team_name}: 近{len(recent)}场 = {points}分 (WC)")
    return points, len(recent), "api"


def _compute_h2h_from_wc(home, away):
    """
    从世界杯完赛数据中查找两队历史交锋。
    只查 WC 赛事内的交锋（可能为 0）。
    返回: dict 或 None
    """
    matches = _fetch_all_finished_wc_matches()
    if not matches:
        return None

    hw = dw = aw = 0
    for m in matches:
        teams = {m["home"], m["away"]}
        if home not in teams or away not in teams:
            continue
        if m["home"] == home:
            if m["home_score"] > m["away_score"]:
                hw += 1
            elif m["home_score"] == m["away_score"]:
                dw += 1
            else:
                aw += 1
        else:
            if m["away_score"] > m["home_score"]:
                hw += 1
            elif m["away_score"] == m["home_score"]:
                dw += 1
            else:
                aw += 1

    total = hw + dw + aw
    if total == 0:
        return None

    log.info(f"  {home} vs {away}: WC交锋 {hw}胜{dw}平{aw}负 (API)")
    return {"home_wins": hw, "draws": dw, "away_wins": aw,
            "total": total, "source": "api"}


# ============================================================
# 近期状态（API 优先 → CSV 兜底）
# ============================================================

def _fetch_recent_form(home, away):
    """
    获取两队近5场积分。
    优先级: WC完赛数据 → CSV → 默认值
    """
    fh, fh_n, fh_src = _compute_recent_form_from_wc(home)
    fa, fa_n, fa_src = _compute_recent_form_from_wc(away)

    # 如果 WC 数据不足 3 场，补 CSV
    need_csv_h = (fh is None or fh_n < 3)
    need_csv_a = (fa is None or fa_n < 3)

    if need_csv_h or need_csv_a:
        csv_path = TEMPLATES_DIR / "recent_form.csv"
        if csv_path.exists():
            with open(csv_path, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if need_csv_h and row.get("球队", "") == home:
                        fh = int(row.get("近5场积分", DEFAULT_RECENT_POINTS))
                        fh_src = "csv"
                        need_csv_h = False
                    if need_csv_a and row.get("球队", "") == away:
                        fa = int(row.get("近5场积分", DEFAULT_RECENT_POINTS))
                        fa_src = "csv"
                        need_csv_a = False

    # 最终兜底
    if fh is None:
        fh = DEFAULT_RECENT_POINTS
        fh_src = "default"
    if fa is None:
        fa = DEFAULT_RECENT_POINTS
        fa_src = "default"

    source = "api" if (fh_src == "api" and fa_src == "api") else (
             "mixed" if (fh_src in ("api","csv") and fa_src in ("api","csv")) else fh_src)
    return fh, fa, source


# ============================================================
# 历史交锋（WC数据 → CSV 兜底）
# ============================================================

def _fetch_h2h(home, away):
    """
    获取历史交锋。
    优先级: WC完赛数据 → CSV → None
    """
    result = _compute_h2h_from_wc(home, away)
    if result:
        return result

    csv_path = TEMPLATES_DIR / "h2h.csv"
    if csv_path.exists():
        with open(csv_path, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("主队", "") == home and row.get("客队", "") == away:
                    hw = int(row.get("主胜", 2))
                    dw = int(row.get("平局", 2))
                    aw = int(row.get("客胜", 1))
                    return {
                        "home_wins": hw, "draws": dw, "away_wins": aw,
                        "total": hw + dw + aw, "source": "csv",
                    }
    return None


# ============================================================
# 综合采集
# ============================================================

def collect_match_data(match):
    """综合采集一场比赛的全部数据"""
    home, away = match["home"], match["away"]
    data = {"match": match, "home": home, "away": away, "data_status": {}}

    # 赔率
    odds = fetch_odds(home, away)
    data["odds"] = odds
    data["data_status"]["odds"] = odds["source"] if odds else "missing"

    # FIFA 排名
    rh, ra = fetch_fifa_ranking(home), fetch_fifa_ranking(away)
    data["fifa_rank"] = {"home": rh, "away": ra}
    data["data_status"]["fifa"] = "ok" if (rh and ra) else ("partial" if (rh or ra) else "missing")

    # 伤停
    inj = fetch_injuries(home, away)
    data["injuries"] = inj
    data["data_status"]["injuries"] = inj["source"]

    # 历史交锋（WC自动 → CSV）
    h2h = _fetch_h2h(home, away)
    data["h2h"] = h2h
    data["data_status"]["h2h"] = h2h["source"] if h2h else "missing"

    # 近期状态（WC自动 → CSV → 默认）
    fh, fa, src = _fetch_recent_form(home, away)
    data["recent_form"] = {"home": fh, "away": fa}
    data["data_status"]["recent_form"] = src

    return data
