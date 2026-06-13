"""
每日三注推荐：串关 + 单关 + 混合
基于当日所有比赛的综合分析，生成可直接下单的三注方案
"""

from names import cn


def generate_daily_bets(results):
    """
    输入: list of analyze_match() 返回值
    输出: dict with parlay, single, mixed recommendations
    """
    if not results:
        return None

    # 按"赢面"排序（概率 × 风险系数）
    scored = []
    for r in results:
        probs = r["probabilities"]
        max_prob = max(probs["home_win"], probs["draw"], probs["away_win"])
        max_idx = [probs["home_win"], probs["draw"], probs["away_win"]].index(max_prob)
        labels = ["主胜", "平局", "客胜"]

        # 风险系数：低=1.0, 中=0.85, 高=0.6
        risk = r["risk_level"]
        risk_factor = {"低风险": 1.0, "中风险": 0.85, "高风险": 0.6}.get(risk, 0.7)

        # 赢面分 = 概率 × 风险系数
        confidence = max_prob * risk_factor

        scored.append({
            "result": r,
            "max_prob": max_prob,
            "max_label": labels[max_idx],
            "risk": risk,
            "confidence": confidence,
            "home": r["home"],
            "away": r["away"],
            "home_cn": cn(r["home"]),
            "away_cn": cn(r["away"]),
        })

    scored.sort(key=lambda x: x["confidence"], reverse=True)

    # 过滤掉高风险场次
    safe = [s for s in scored if s["risk"] != "高风险"]
    all_bets = safe if safe else scored  # 如果全是高风险就用全部

    bets = {}

    # ============================================================
    # 1. 串关推荐 (2串1 或 3串1)
    # ============================================================
    if len(all_bets) >= 3 and all_bets[0]["confidence"] >= 0.35:
        top3 = all_bets[:3]
        combo = " + ".join(
            f'{cn(b["home"])}vs{cn(b["away"])} [{b["max_label"]}]'
            for b in top3
        )
        total_conf = sum(b["confidence"] for b in top3) / 3
        if total_conf >= 0.50:
            amount = "30-50元"
            label = "⭐ 稳胆3串1"
        else:
            amount = "20-30元"
            label = "📌 进取3串1"

        bets["parlay"] = {
            "type": "3串1",
            "label": label,
            "picks": combo,
            "amount": amount,
            "matches": [f'{cn(b["home"])} {b["max_label"]}' for b in top3],
        }
    elif len(all_bets) >= 2:
        top2 = all_bets[:2]
        combo = " + ".join(
            f'{cn(b["home"])}vs{cn(b["away"])} [{b["max_label"]}]'
            for b in top2
        )
        bets["parlay"] = {
            "type": "2串1",
            "label": "⭐ 稳胆2串1",
            "picks": combo,
            "amount": "30-80元",
            "matches": [f'{cn(b["home"])} {b["max_label"]}' for b in top2],
        }
    else:
        bets["parlay"] = {
            "type": "—",
            "label": "今日场次不足，不推荐串关",
            "picks": "",
            "amount": "",
            "matches": [],
        }

    # ============================================================
    # 2. 单关推荐（最有信心的单场）
    # ============================================================
    if all_bets:
        best = all_bets[0]
        home_cn = cn(best["home"])
        away_cn = cn(best["away"])

        if best["risk"] == "低风险" and best["max_prob"] >= 0.55:
            amount = "50-100元"
            label = "💎 今日重心单关"
        elif best["risk"] == "低风险":
            amount = "30-50元"
            label = "⭐ 稳健单关"
        elif best["confidence"] >= 0.35:
            amount = "20-30元"
            label = "📌 精选单关"
        else:
            amount = "10-20元"
            label = "🎯 娱乐单关"

        bets["single"] = {
            "label": label,
            "match": f"{home_cn} vs {away_cn}",
            "pick": f"{best['max_label']}",
            "odds_hint": f"概率{best['max_prob']:.0%}",
            "amount": amount,
        }
    else:
        bets["single"] = {"label": "今日不建议单关", "match": "", "pick": "", "amount": ""}

    # ============================================================
    # 3. 混合推荐（单关 + 小串 或 双选组合）
    # ============================================================
    if len(all_bets) >= 2:
        best = all_bets[0]
        second = all_bets[1]
        home1, away1 = cn(best["home"]), cn(best["away"])
        home2, away2 = cn(second["home"]), cn(second["away"])

        # 主推的单关 + 第二场的双选防平
        probs2 = second["result"]["probabilities"]
        dir2 = "胜+平" if probs2["home_win"] > probs2["away_win"] else "平+负"

        bets["mixed"] = {
            "label": "🔄 混合过关",
            "description": f"单关+双选组合",
            "leg1": f"① 单关: {home1}vs{away1} [{best['max_label']}]",
            "leg2": f"② 双选: {home2}vs{away2} [{dir2}]",
            "amount": "30-50元",
        }
    else:
        bets["mixed"] = {"label": "今日场次不足", "description": "", "amount": ""}

    return bets


def format_daily_bets(bets):
    """格式化为输出文本"""
    if not bets:
        return ""

    lines = []
    lines.append("")
    lines.append("╔══════════════════════════════════╗")
    lines.append("║     📋 今日三注 — 直接下单       ║")
    lines.append("╚══════════════════════════════════╝")
    lines.append("")

    # 串关
    p = bets.get("parlay", {})
    lines.append(f"  【第一注】{p.get('label', '')}")
    lines.append(f"  类型: {p.get('type', '')}")
    lines.append(f"  选项: {p.get('picks', '')}")
    if p.get('amount'):
        lines.append(f"  金额: {p.get('amount', '')}")
    lines.append("")

    # 单关
    s = bets.get("single", {})
    lines.append(f"  【第二注】{s.get('label', '')}")
    lines.append(f"  场次: {s.get('match', '')}")
    lines.append(f"  选项: {s.get('pick', '')} ({s.get('odds_hint', '')})")
    if s.get('amount'):
        lines.append(f"  金额: {s.get('amount', '')}")
    lines.append("")

    # 混合
    m = bets.get("mixed", {})
    lines.append(f"  【第三注】{m.get('label', '')}")
    lines.append(f"  {m.get('description', '')}")
    if m.get('leg1'):
        lines.append(f"  {m.get('leg1', '')}")
    if m.get('leg2'):
        lines.append(f"  {m.get('leg2', '')}")
    if m.get('amount'):
        lines.append(f"  金额: {m.get('amount', '')}")
    lines.append("")

    lines.append("  ────────────────────────────────")
    lines.append("  💡 打开体彩App → 选择对应场次 → 照此下单")
    lines.append("")

    return "\n".join(lines)
