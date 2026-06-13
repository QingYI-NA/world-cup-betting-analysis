"""
每日串关推荐：基于每场最佳盘口，构建综合串关
"""

from names import cn


def build_parlay(results):
    """
    从所有比赛中挑选最佳盘口，构建串关。
    只选置信度足够的场次。
    返回 dict 或 None
    """
    if len(results) < 2:
        return None

    picks = []
    for r in results:
        pick = _pick_best_market(r)
        if pick:
            picks.append(pick)

    if len(picks) < 2:
        return None

    # 按置信度排序，取前4场
    picks.sort(key=lambda x: x["confidence"], reverse=True)
    selected = picks[:4]  # 最多4串1

    total_conf = sum(p["confidence"] for p in selected) / len(selected)

    if total_conf >= 0.50:
        label = "⭐ 稳胆串关"
        amount = "50-100元"
    elif total_conf >= 0.35:
        label = "📌 精选串关"
        amount = "30-50元"
    else:
        label = "🎯 娱乐串关"
        amount = "10-20元"

    return {
        "label": label,
        "type": f"{len(selected)}串1",
        "picks": selected,
        "amount": amount,
        "total_confidence": total_conf,
    }


def _pick_best_market(result):
    """
    从一场比赛中选择最有投注价值的盘口。
    返回 dict 或 None（该场不值得投注）
    """
    probs = [
        result["probabilities"]["home_win"],
        result["probabilities"]["draw"],
        result["probabilities"]["away_win"],
    ]
    risk = result["risk_level"]
    scores = result.get("dimension_scores", {})
    sh = scores.get("home", {})
    sa = scores.get("away", {})
    total = result.get("total_scores", {})
    h_total = total.get("home", 5)
    a_total = total.get("away", 5)
    strength_gap = h_total - a_total

    home_cn = cn(result["home"])
    away_cn = cn(result["away"])
    max_prob = max(probs)
    max_idx = probs.index(max_prob)
    labels = ["主胜", "平局", "客胜"]

    # 高风险场次：不选入串关
    if risk == "高风险":
        return None

    candidates = []

    # 候选1: 胜平负（概率最高选项）
    if max_prob >= 0.38:
        candidates.append({
            "market": "胜平负",
            "pick": labels[max_idx],
            "odds_note": f"概率{max_prob:.0%}",
            "confidence": max_prob * 0.85,
        })

    # 候选2: 让球盘（实力差明显时）
    if abs(strength_gap) >= 1.0:
        if strength_gap >= 1.0:
            candidates.append({
                "market": "让球盘",
                "pick": f"{home_cn} -0.5",
                "odds_note": f"让半球",
                "confidence": min(0.55 + abs(strength_gap) * 0.05, 0.75),
            })
        else:
            candidates.append({
                "market": "让球盘",
                "pick": f"{away_cn} -0.5",
                "odds_note": f"让半球",
                "confidence": min(0.55 + abs(strength_gap) * 0.05, 0.75),
            })

    # 候选3: 大小球（强弱分明或伤停严重时）
    h_injury = sh.get("injuries", 10)
    a_injury = sa.get("injuries", 10)
    o_score = sh.get("odds_market", 5)
    d_score = sa.get("odds_market", 5)

    if o_score >= 7 and d_score <= 3:
        candidates.append({
            "market": "大小球",
            "pick": "小 2.5球",
            "odds_note": "强队控场",
            "confidence": 0.50,
        })
    elif h_injury <= 3 or a_injury <= 3:
        candidates.append({
            "market": "大小球",
            "pick": "小 2.5球",
            "odds_note": "核心缺阵",
            "confidence": 0.48,
        })

    # 候选4: 双方进球（实力接近时）
    if abs(strength_gap) < 0.5 and h_injury >= 8 and a_injury >= 8:
        candidates.append({
            "market": "双方进球",
            "pick": "是",
            "odds_note": "实力接近",
            "confidence": 0.45,
        })

    if not candidates:
        return None

    # 选置信度最高的
    best = max(candidates, key=lambda x: x["confidence"])

    # 低置信度不选
    if best["confidence"] < 0.35:
        return None

    return {
        "match": f"{home_cn} vs {away_cn}",
        "market": best["market"],
        "pick": best["pick"],
        "odds_note": best["odds_note"],
        "confidence": best["confidence"],
    }


def format_parlay(parlay):
    """格式化串关输出"""
    if not parlay:
        return ""

    lines = []
    lines.append("")
    lines.append("╔══════════════════════════════════╗")
    lines.append("║       📋 今日串关推荐             ║")
    lines.append("╚══════════════════════════════════╝")
    lines.append("")

    for i, p in enumerate(parlay["picks"], 1):
        lines.append(f"  {i}. {p['match']}")
        lines.append(f"     [{p['market']}] {p['pick']}  ({p['odds_note']})")

    lines.append("")
    lines.append(f"  {parlay['label']}: {parlay['type']}")
    lines.append(f"  金额: {parlay['amount']}")
    lines.append("")
    lines.append("  💡 打开体彩App → 串关投注 → 照此选择")
    lines.append("")

    return "\n".join(lines)
