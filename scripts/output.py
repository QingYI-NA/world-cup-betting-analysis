"""
输出层：控制台格式化输出 + JSON/CSV 持久化
"""

import json
import csv
from datetime import datetime, timezone, timedelta
from pathlib import Path

from config import (
    ANALYSIS_DIR, WEIGHTS, DISCLAIMER, TOURNAMENT,
)

BEIJING_TZ = timezone(timedelta(hours=8))


def _utc_to_beijing(utc_str):
    """UTC ISO 时间 → 北京时间字符串"""
    if not utc_str:
        return "时间待定"
    try:
        s = utc_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        bj = dt.astimezone(BEIJING_TZ)
        return bj.strftime("%m-%d %H:%M") + " 北京时间"
    except Exception:
        return utc_str[:16].replace("T", " ")


def _generate_all_tiers(probs, risk_level):
    """
    生成三级方案：小额 / 稳健 / 博高赔
    返回 list of dict
    """
    max_idx = probs.index(max(probs))
    labels = ["主胜", "平局", "客胜"]
    tiers = []

    # 小额娱乐档（永远推荐）
    tiers.append({
        "tier": "🥉 小额娱乐",
        "amount": "10-30元",
        "suggestion": f"单关 {labels[max_idx]}",
    })

    # 稳健尝试档（中低风险才推荐）
    if risk_level in ("低风险", "中风险"):
        if risk_level == "低风险":
            tiers.append({
                "tier": "🥈 稳健尝试",
                "amount": "30-80元",
                "suggestion": f"2串1（{labels[max_idx]} + 另一场低风险）",
            })
        else:
            direction = "胜+平" if probs[0] > probs[2] else "平+负"
            tiers.append({
                "tier": "🥈 稳健尝试",
                "amount": "20-50元",
                "suggestion": f"双选 {direction}",
            })

    # 博高赔档（高风险才推荐跳过）
    if risk_level == "高风险":
        tiers.append({
            "tier": "🥇 博高赔",
            "amount": f"≤10元",
            "suggestion": f"娱乐单关最高赔（10元以内）",
        })
        tiers.append({"tier": "⚠️ 风险提示", "amount": "", "suggestion": "冷门概率高，不建议重注"})
    else:
        tiers.append({
            "tier": "🥇 博高赔",
            "amount": "10-20元",
            "suggestion": f"搏冷门 {labels[2 - max_idx]}（小注娱乐）",
        })

    return tiers


def format_console_report(results):
    """
    格式化控制台输出。
    results: list of analyze_match() 返回值
    """
    lines = []
    sep = "=" * 52

    for i, r in enumerate(results):
        match = r["match"]
        home = r["home"]
        away = r["away"]
        kickoff = _utc_to_beijing(match.get("kickoff", ""))
        stage = match.get("stage", "").replace("GROUP_STAGE", "小组赛").replace("KNOCKOUT_STAGE", "淘汰赛")

        lines.append(sep)
        lines.append(f"  {kickoff}")
        lines.append(f"  {home} vs {away}（{stage}）")
        lines.append(sep)

        # 数据状态
        ds = r.get("data_status", {})
        status_icons = []
        for k, v in ds.items():
            icon = "✅" if v in ("ok", "api", "csv_fresh") else ("⚠️" if v in ("csv_stale", "cache_stale", "partial") else "❌")
            status_icons.append(f"{k}={v}")
        lines.append(f"  [数据] {' | '.join(status_icons)}")

        # 六维度得分
        dims = r.get("dimension_scores", {})
        sh = dims.get("home", {})
        sa = dims.get("away", {})
        dim_labels = {
            "team_strength": "硬实力",
            "recent_form": "近状态",
            "injuries": "伤停  ",
            "head_to_head": "交锋  ",
            "external": "场外  ",
            "odds_market": "赔率  ",
        }
        lines.append(f"  [六维得分]")
        for dim, label in dim_labels.items():
            h_score = sh.get(dim, 5)
            a_score = sa.get(dim, 5)
            extra = ""
            if dim == "injuries":
                raw = r.get("raw", {})
                hn = raw.get("injuries_home", "?")
                an = raw.get("injuries_away", "?")
                if hn != "无" and hn != "?":
                    extra = f"[{home}:{hn}]"
                if an != "无" and an != "?":
                    extra += f" [{away}:{an}]"
            elif dim == "head_to_head":
                raw = r.get("raw", {})
                h2h_info = raw.get("h2h", "")
                if h2h_info and h2h_info != "无数据":
                    extra = f"({h2h_info})"
            elif dim == "odds_market":
                raw = r.get("raw", {})
                oi = raw.get("odds_implied", "")
                if oi and oi != "无赔率数据":
                    extra = f"[{oi}]"
            line = f"    {label}: {home} {h_score:.1f}  vs  {away} {a_score:.1f}"
            if extra:
                line += f"  {extra}"
            lines.append(line)

        # 综合概率
        probs = r.get("probabilities", {})
        ph = probs.get('home_win', 0)
        pd = probs.get('draw', 0)
        pa = probs.get('away_win', 0)
        lines.append(f"  [概率] 主 {ph:.0%}  |  平 {pd:.0%}  |  客 {pa:.0%}")

        # 风险
        risk = r.get("risk_level", "未知")
        risk_icon = {"低风险": "🟢", "中风险": "🟡", "高风险": "🔴"}.get(risk, "⚪")
        lines.append(f"  [风险] {risk_icon} {risk}")

        # 一句话结论
        lines.append(f"  [结论] {r.get('oneliner', '')}")

        # 三级方案
        tiers = _generate_all_tiers([ph, pd, pa], risk)
        lines.append(f"  [方案]")
        for t in tiers:
            amt = f"({t['amount']})" if t['amount'] else ""
            lines.append(f"    {t['tier']}: {t['suggestion']} {amt}")
        for w in r.get("proposal", {}).get("warnings", []):
            lines.append(f"    ⚠ {w}")

        lines.append("")

    lines.append(f"  {DISCLAIMER}")
    lines.append(sep)
    lines.append(f"  分析: {datetime.now().strftime('%Y-%m-%d %H:%M')} 北京时间 | {TOURNAMENT}")
    lines.append("")

    return "\n".join(lines)


def format_compact_report(results):
    """
    紧凑版输出（适合飞书推送）。
    """
    if not results:
        return "⚽ 今日无世界杯比赛"

    lines = [f"⚽ {TOURNAMENT} 每日分析", f"{datetime.now().strftime('%m-%d %H:%M')} 北京时间", ""]

    for r in results:
        home = r["home"]
        away = r["away"]
        probs = r.get("probabilities", {})
        risk = r.get("risk_level", "")
        risk_icon = {"低风险": "🟢", "中风险": "🟡", "高风险": "🔴"}.get(risk, "⚪")
        kickoff = _utc_to_beijing(r["match"].get("kickoff", ""))

        ph = probs.get("home_win", 0)
        pd = probs.get("draw", 0)
        pa = probs.get("away_win", 0)

        lines.append(f"{risk_icon} {home} vs {away}")
        lines.append(f"   ⏰ {kickoff}")
        lines.append(f"   📊 主{ph:.0%} 平{pd:.0%} 客{pa:.0%}")
        lines.append(f"   💬 {r.get('oneliner', '')}")

        tiers = _generate_all_tiers([ph, pd, pa], risk)
        for t in tiers:
            amt = f" ({t['amount']})" if t['amount'] else ""
            lines.append(f"   {t['tier']}: {t['suggestion']}{amt}")

        lines.append("")

    lines.append(f"--- {DISCLAIMER}")
    return "\n".join(lines)


def save_results(results):
    """持久化分析结果到 JSON 和 CSV"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    basename = f"analysis_{date_str}"

    # JSON
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

    # CSV
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
                "主队": r["home"],
                "客队": r["away"],
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
