"""
多盘口投注建议生成器
基于六维度分析结果，生成胜平负、让球、大小球、双方进球等建议
"""

from config import MAX_HIGH_RISK_AMOUNT


def generate_advice(result):
    """
    输入: analyze_match() 返回值
    输出: {
        "win_draw_loss": str,    # 胜平负建议
        "asian_handicap": str,   # 让球盘建议
        "over_under": str,       # 大小球建议
        "btts": str,             # 双方进球
        "ht_ft": str,            # 半全场
        "score_hint": str,       # 波胆参考
        "tiers": [...]           # 三级方案
    }
    """
    probs = [
        result["probabilities"]["home_win"],
        result["probabilities"]["draw"],
        result["probabilities"]["away_win"],
    ]
    risk = result["risk_level"]
    odds = result.get("match", {}).get("odds") or result.get("odds")
    scores = result.get("dimension_scores", {})
    home_name = result["home"]
    away_name = result["away"]

    sh = scores.get("home", {})
    sa = scores.get("away", {})
    h_total = result.get("total_scores", {}).get("home", 5)
    a_total = result.get("total_scores", {}).get("away", 5)

    # 实力差 (正=主强)
    strength_gap = h_total - a_total
    max_prob = max(probs)
    max_idx = probs.index(max_prob)
    labels = ["主胜", "平局", "客胜"]

    advice = {}

    # ============================================================
    # 1. 胜平负 (1X2)
    # ============================================================
    if risk == "高风险":
        advice["win_draw_loss"] = "❌ 不建议单关重注，娱乐为主"
    elif max_prob >= 0.55:
        advice["win_draw_loss"] = f"⭐ 主推 {labels[max_idx]}（概率{max_prob:.0%}）"
    elif max_prob >= 0.40:
        advice["win_draw_loss"] = f"📌 倾向 {labels[max_idx]}（{max_prob:.0%}），建议双选防平"
    else:
        advice["win_draw_loss"] = f"⚖️ 三方接近，建议双选 {'胜+平' if probs[0] > probs[2] else '平+负'}"

    # ============================================================
    # 2. 让球盘 (Asian Handicap)
    # ============================================================
    if risk == "高风险":
        advice["asian_handicap"] = "⚠️ 不建议碰让球盘"
    elif strength_gap >= 2.0:
        advice["asian_handicap"] = f"🏠 {home_name} -0.5/-1（主队让半球到一球）"
    elif strength_gap >= 1.0:
        advice["asian_handicap"] = f"🏠 {home_name} -0.5（主队让半球）"
    elif strength_gap >= 0.2:
        advice["asian_handicap"] = f"⚖️ 平手盘，略倾向 {home_name if strength_gap > 0 else away_name}"
    elif strength_gap >= -1.0:
        advice["asian_handicap"] = f"✈️ {away_name} -0.5（客队让半球）"
    else:
        advice["asian_handicap"] = f"✈️ {away_name} -0.5/-1（客队让半球到一球）"

    # ============================================================
    # 3. 大小球 (Over/Under 2.5)
    # ============================================================
    # 从球队风格推断：进攻型 → 大球，防守型 → 小球
    h_injury = sh.get("injuries", 10)
    a_injury = sa.get("injuries", 10)
    o_score = sh.get("odds_market", 5)
    d_score = sa.get("odds_market", 5)

    # 强队伤病多 + 赔率倾向一边 → 小球
    # 双方实力接近 + 进攻型 → 大球
    if o_score >= 8 or d_score <= 2:
        advice["over_under"] = "📉 倾向 小2.5球（强队碾压节奏慢）"
    elif abs(strength_gap) < 0.5 and h_injury >= 6 and a_injury >= 6:
        advice["over_under"] = "📈 倾向 大2.5球（实力接近 + 阵容齐整）"
    elif h_injury <= 3 or a_injury <= 3:
        advice["over_under"] = "📉 倾向 小2.5球（核心缺阵影响进攻）"
    elif max_prob >= 0.55:
        advice["over_under"] = "📉 倾向 小2.5球（强弱分明，强队控场）"
    else:
        advice["over_under"] = "⚖️ 大小球五五开，小注娱乐"

    # ============================================================
    # 4. 双方进球 (BTTS)
    # ============================================================
    if h_injury <= 3 or a_injury <= 3:
        advice["btts"] = "❌ 否（核心缺阵影响进攻端）"
    elif abs(strength_gap) < 0.8 and h_injury >= 8 and a_injury >= 8:
        advice["btts"] = "✅ 是（实力接近 + 阵容齐整）"
    elif strength_gap > 2.0:
        advice["btts"] = "❌ 否（强弱分明，弱队难进球）"
    elif strength_gap < -2.0:
        advice["btts"] = "❌ 否（强弱分明，弱队难进球）"
    else:
        advice["btts"] = "⚖️ 可搏 是（娱乐注）"

    # ============================================================
    # 5. 半全场 (HT/FT)
    # ============================================================
    if risk == "低风险" and max_prob >= 0.55:
        if max_idx == 0:
            advice["ht_ft"] = f"🏠 主/主（{home_name}半场领先→全场胜）"
        elif max_idx == 2:
            advice["ht_ft"] = f"✈️ 客/客（{away_name}半场领先→全场胜）"
        else:
            advice["ht_ft"] = "⚖️ 平/平（搏闷平）"
    elif strength_gap > 1.5:
        advice["ht_ft"] = f"🏠 平/主 或 主/主（{home_name}后程发力）"
    elif strength_gap < -1.5:
        advice["ht_ft"] = f"✈️ 平/客 或 客/客（{away_name}后程发力）"
    elif risk == "高风险":
        advice["ht_ft"] = "⚠️ 不推荐半全场（冷门概率高）"
    else:
        advice["ht_ft"] = "⚖️ 平/平 或 平/主（胶着局小注）"

    # ============================================================
    # 6. 波胆参考
    # ============================================================
    if risk == "低风险" and max_prob >= 0.55:
        if max_idx == 0:
            advice["score_hint"] = "2-0, 2-1（主胜）"
        elif max_idx == 2:
            advice["score_hint"] = "0-2, 1-2（客胜）"
        else:
            advice["score_hint"] = "1-1, 0-0（平局）"
    elif risk == "中风险":
        if max_idx == 0:
            advice["score_hint"] = "1-0, 2-1, 1-1（主队不败）"
        elif max_idx == 2:
            advice["score_hint"] = "0-1, 1-2, 1-1（客队不败）"
        else:
            advice["score_hint"] = "1-1, 0-0, 1-0（平局首选）"
    else:
        advice["score_hint"] = "不建议波胆（高风险）"

    # ============================================================
    # 7. 三级方案
    # ============================================================
    tiers = []
    tiers.append({"tier": "🥉 小额娱乐", "amount": "10-30元", "suggestion": f"单关 {labels[max_idx]}"})

    if risk == "低风险":
        tiers.append({"tier": "🥈 稳健尝试", "amount": "30-80元", "suggestion": f"2串1（{labels[max_idx]} + 另一场低风险）"})
        tiers.append({"tier": "🥇 博高赔", "amount": "10-20元", "suggestion": f"比分波胆 {advice['score_hint']} + 半全场"})
    elif risk == "中风险":
        direction = "胜+平" if probs[0] > probs[2] else "平+负"
        tiers.append({"tier": "🥈 稳健尝试", "amount": "20-50元", "suggestion": f"双选 {direction}"})
        tiers.append({"tier": "🥇 博高赔", "amount": "10-20元", "suggestion": f"小2.5球 + {'双方进球否' if '否' in advice['btts'] else '比分波胆'}"})
    else:
        tiers.append({"tier": "🥈 谨慎观望", "amount": f"≤{MAX_HIGH_RISK_AMOUNT}元", "suggestion": f"娱乐单关最高赔（{MAX_HIGH_RISK_AMOUNT}元以内）"})
        tiers.append({"tier": "⚠️ 风险提示", "amount": "", "suggestion": "冷门概率高，不建议重注任何盘口"})

    advice["tiers"] = tiers
    return advice
