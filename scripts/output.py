"""
输出层：控制台格式化输出 + JSON/CSV 持久化
v4: 中文名 + 多盘口建议
"""

import json
import csv
from datetime import datetime, timezone, timedelta
from pathlib import Path

from config import ANALYSIS_DIR, DISCLAIMER, TOURNAMENT
from names import cn, venue_cn, home_away_label
from betting_advice import generate_advice
from daily_summary import build_parlay, format_parlay

BEIJING_TZ = timezone(timedelta(hours=8))


def _utc_to_beijing(utc_str):
    if not utc_str:
        return "时间待定"
    try:
        s = utc_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        bj = dt.astimezone(BEIJING_TZ)
        return bj.strftime("%m-%d %H:%M") + " 北京时间"
    except Exception:
        return utc_str[:16].replace("T", " ")


def _format_bar(home_score, away_score, width=16):
    """可视化得分条"""
    total = max(home_score + away_score, 0.1)
    h_bar = int(home_score / total * width)
    a_bar = width - h_bar
    return f"{'█' * h_bar}{'░' * a_bar}"


def format_console_report(results):
    lines = []
    sep = "=" * 54

    for r in results:
        match = r["match"]
        home = match["home"]
        away = match["away"]
        home_cn = cn(home)
        away_cn = cn(away)

        kickoff = _utc_to_beijing(match.get("kickoff", ""))
        stage = match.get("stage", "").replace("GROUP_STAGE", "小组赛").replace("KNOCKOUT_STAGE", "淘汰赛")
        venue_id = match.get("venue_id", "")
        venue_name = venue_cn(venue_id) if venue_id else ""

        lines.append(sep)
        lines.append(f"  {kickoff}")
        lines.append(f"  🏠 {home_cn}  vs  ✈️ {away_cn}   {stage}")
        if venue_name:
            lines.append(f"  📍 {venue_name}")
        lines.append(sep)

        # 数据状态
        ds = r.get("data_status", {})
        icons = []
        for k, v in ds.items():
            icon = "✅" if v in ("ok", "api", "csv_fresh", "mcp") else (
                   "⚠️" if v in ("csv_stale", "cache_stale", "partial") else "❌")
            icons.append(f"{k}={v}")
        lines.append(f"  [数据] {' | '.join(icons)}")

        # 核心指标行
        probs = r.get("probabilities", {})
        ph, pd, pa = probs.get('home_win', 0), probs.get('draw', 0), probs.get('away_win', 0)
        risk = r.get("risk_level", "")
        risk_icon = {"低风险": "🟢", "中风险": "🟡", "高风险": "🔴"}.get(risk, "⚪")

        raw = r.get("raw", {})
        rh, ra = raw.get("rank_home", "?"), raw.get("rank_away", "?")
        inj_h = raw.get("injuries_home", "无")
        inj_a = raw.get("injuries_away", "无")
        odds_info = raw.get("odds_implied", "")

        lines.append(f"  FIFA: #{rh} vs #{ra}  |  概率: 主{ph:.0%} 平{pd:.0%} 客{pa:.0%}  |  {risk_icon} {risk}")
        if inj_h != "无" or inj_a != "无":
            lines.append(f"  伤停: {home_cn}[{inj_h}]  {away_cn}[{inj_a}]")
        if odds_info and odds_info != "无赔率数据":
            lines.append(f"  赔率隐含: {odds_info}")

        # 一句话
        lines.append(f"  💬 {r.get('oneliner', '')}")

        # ===== 多盘口建议 =====
        advice = generate_advice(r)
        lines.append(f"  {'─' * 40}")
        lines.append(f"  [投注建议]")
        lines.append(f"  胜平负:  {advice['win_draw_loss']}")
        lines.append(f"  让球盘:  {advice['asian_handicap']}")
        lines.append(f"  大小球:  {advice['over_under']}")
        lines.append(f"  双方进球:{advice['btts']}")
        lines.append(f"  半全场:  {advice['ht_ft']}")
        lines.append(f"  波胆参考:{advice['score_hint']}")

        # 三级方案
        lines.append(f"  {'─' * 40}")
        lines.append(f"  [分层方案]")
        for t in advice.get("tiers", []):
            amt = f"({t['amount']})" if t['amount'] else ""
            lines.append(f"    {t['tier']}: {t['suggestion']} {amt}")

        lines.append("")

    lines.append(f"  {DISCLAIMER}")
    lines.append(sep)
    lines.append(f"  分析: {datetime.now().strftime('%Y-%m-%d %H:%M')} 北京时间 | {TOURNAMENT}")

    # 每日串关推荐
    parlay = build_parlay(results)
    lines.append(format_parlay(parlay))

    lines.append("")
    return "\n".join(lines)


def format_compact_report(results):
    """紧凑版（飞书推送）"""
    if not results:
        return "⚽ 今日无世界杯比赛"

    lines = [f"⚽ {TOURNAMENT} 每日分析", f"{datetime.now().strftime('%m-%d %H:%M')} 北京时间", ""]

    for r in results:
        home = r["home"]
        away = r["away"]
        home_cn = cn(home)
        away_cn = cn(away)
        probs = r.get("probabilities", {})
        risk = r.get("risk_level", "")
        risk_icon = {"低风险": "🟢", "中风险": "🟡", "高风险": "🔴"}.get(risk, "⚪")
        kickoff = _utc_to_beijing(r["match"].get("kickoff", ""))
        venue_id = r["match"].get("venue_id", "")
        venue_name = venue_cn(venue_id) if venue_id else ""
        raw = r.get("raw", {})

        ph, pd, pa = probs.get('home_win', 0), probs.get('draw', 0), probs.get('away_win', 0)
        lines.append(f"{risk_icon} {home_cn} vs {away_cn}")
        lines.append(f"   ⏰ {kickoff}")
        if venue_name:
            lines.append(f"   📍 {venue_name}")
        rh, ra = raw.get("rank_home", "?"), raw.get("rank_away", "?")
        lines.append(f"   FIFA #{rh} vs #{ra}  |  主{ph:.0%} 平{pd:.0%} 客{pa:.0%}")

        # 多盘口精简版
        advice = generate_advice(r)
        lines.append(f"   胜平负: {advice['win_draw_loss']}")
        lines.append(f"   让球: {advice['asian_handicap']}")
        lines.append(f"   大小球: {advice['over_under']}")

        for t in advice.get("tiers", []):
            amt = f" ({t['amount']})" if t['amount'] else ""
            lines.append(f"   {t['tier']}: {t['suggestion']}{amt}")

        lines.append("")

    lines.append(f"--- {DISCLAIMER}")

    # 串关推荐
    parlay = build_parlay(results)
    if parlay:
        lines.append("")
        lines.append(f"📋 今日串关 ({parlay['type']}):")
        for p in parlay["picks"]:
            lines.append(f"  {p['match']} [{p['market']}] {p['pick']}")
        lines.append(f"  💰 {parlay['amount']}")

    return "\n".join(lines)


def save_results(results):
    date_str = datetime.now().strftime("%Y-%m-%d")
    basename = f"analysis_{date_str}"

    json_path = ANALYSIS_DIR / f"{basename}.json"
    existing = []
    if json_path.exists():
        with open(json_path, "r", encoding="utf-8") as f:
            try:
                existing = json.load(f)
            except Exception:
                pass
    existing.extend(results)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2, default=str)

    csv_path = ANALYSIS_DIR / f"{basename}.csv"
    csv_exists = csv_path.exists()
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        fieldnames = [
            "北京时间", "主队", "客队", "阶段",
            "主胜概率", "平局概率", "客胜概率",
            "风险等级", "推荐方案", "金额", "一句话",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not csv_exists:
            writer.writeheader()
        for r in results:
            probs = r.get("probabilities", {})
            proposal = r.get("proposal", {})
            writer.writerow({
                "北京时间": _utc_to_beijing(r["match"].get("kickoff", "")),
                "主队": cn(r["home"]),
                "客队": cn(r["away"]),
                "阶段": r["match"].get("stage", ""),
                "主胜概率": probs.get("home_win", 0),
                "平局概率": probs.get("draw", 0),
                "客胜概率": probs.get("away_win", 0),
                "风险等级": r.get("risk_level", ""),
                "推荐方案": proposal.get("suggestion", ""),
                "金额": proposal.get("amount", ""),
                "一句话": r.get("oneliner", ""),
            })

    return str(json_path), str(csv_path)
