"""
核心分析层：六维度查表打分 + 概率计算 + 风险评级 + 购彩方案生成
"""

import math
import logging
from datetime import datetime

from config import (
    WEIGHTS, INJURY_SCORE, FORM_SCORE, RANK_GAP_SCORE, H2H_SCORE,
    EXTERNAL_BONUS, ODDS_ALIGNMENT_SCORE,
    GOAL_RATIO_SMOOTH, HOME_AWAY_SPLIT, MIN_DRAW_PROB,
    KNOCKOUT_DRAW_BOOST, MAX_DRAW_PROB,
    RISK_THRESHOLDS, DEFAULT_SCORE,
    MAX_HIGH_RISK_AMOUNT, MAX_MEDIUM_RISK_AMOUNT,
    MAX_LOW_RISK_AMOUNT, NEVER_RECOMMEND_COMBO, DISCLAIMER,
)

log = logging.getLogger("analyze")


# ============================================================
# 查表打分工具
# ============================================================

def _lookup(value, table):
    """通用查表：按阈值从高到低匹配，返回对应得分"""
    for threshold, score in table:
        if value >= threshold:
            return score
    return table[-1][1]


def _score_injuries(count):
    if count == 0:
        return INJURY_SCORE["0"]
    elif count == 1:
        return INJURY_SCORE["1"]
    elif count == 2:
        return INJURY_SCORE["2"]
    else:
        return INJURY_SCORE["3+"]


def _score_form(points):
    if points is None:
        return DEFAULT_SCORE
    return _lookup(points, FORM_SCORE)


def _score_rank_gap(gap):
    if gap is None:
        return DEFAULT_SCORE
    return _lookup(gap, RANK_GAP_SCORE)


def _score_h2h(winrate):
    if winrate is None:
        return DEFAULT_SCORE
    return _lookup(winrate, H2H_SCORE)


# ============================================================
# 六维度打分
# ============================================================

def compute_dimension_scores(data):
    """
    输入: collect_match_data 返回的 data dict
    输出: {"scores": {home: {...}, away: {...}}, "bonus": {...}, "raw": {...}}
    """
    scores = {"home": {}, "away": {}}
    bonus = {"home": 0.0, "away": 0.0}
    raw = {}

    # --- 维度1: 球队硬实力 (FIFA排名差) ---
    rank_h = data.get("fifa_rank", {}).get("home")
    rank_a = data.get("fifa_rank", {}).get("away")
    raw["rank_home"] = rank_h
    raw["rank_away"] = rank_a

    if rank_h and rank_a:
        gap = abs(rank_h - rank_a)
        raw["rank_gap"] = gap
        base_score = _score_rank_gap(gap)
        if rank_h < rank_a:
            scores["home"]["team_strength"] = min(base_score + 1, 10)
            scores["away"]["team_strength"] = max(base_score - 1, 1)
        elif rank_a < rank_h:
            scores["home"]["team_strength"] = max(base_score - 1, 1)
            scores["away"]["team_strength"] = min(base_score + 1, 10)
        else:
            scores["home"]["team_strength"] = base_score
            scores["away"]["team_strength"] = base_score
    else:
        scores["home"]["team_strength"] = DEFAULT_SCORE
        scores["away"]["team_strength"] = DEFAULT_SCORE

    # --- 维度2: 近期竞技状态 ---
    rf = data.get("recent_form", {})
    scores["home"]["recent_form"] = _score_form(rf.get("home"))
    scores["away"]["recent_form"] = _score_form(rf.get("away"))
    raw["form_home"] = rf.get("home")
    raw["form_away"] = rf.get("away")

    # --- 维度3: 核心伤停 ---
    inj = data.get("injuries", {})
    scores["home"]["injuries"] = _score_injuries(inj.get("home_count", 0))
    scores["away"]["injuries"] = _score_injuries(inj.get("away_count", 0))
    raw["injuries_home"] = inj.get("home_names", "?")
    raw["injuries_away"] = inj.get("away_names", "?")

    # --- 维度4: 历史交锋 ---
    h2h = data.get("h2h")
    if h2h and h2h.get("total", 0) > 0:
        total = h2h["total"]
        winrate_h = h2h["home_wins"] / total
        winrate_a = h2h["away_wins"] / total
        scores["home"]["head_to_head"] = _score_h2h(winrate_h)
        scores["away"]["head_to_head"] = _score_h2h(winrate_a)
        raw["h2h"] = f"{h2h['home_wins']}胜{h2h['draws']}平{h2h['away_wins']}负"
    else:
        scores["home"]["head_to_head"] = DEFAULT_SCORE
        scores["away"]["head_to_head"] = DEFAULT_SCORE
        raw["h2h"] = "无数据"

    # --- 维度5: 场外环境 ---
    scores["home"]["external"] = 5 + bonus["home"]
    scores["away"]["external"] = 5 + bonus["away"]
    raw["external_note"] = "默认中性（可在external.csv补充）"

    # --- 维度6: 赔率市场倾向 ---
    odds = data.get("odds")
    if odds:
        imp_home = 1.0 / odds["home"]
        imp_draw = 1.0 / odds["draw"]
        imp_away = 1.0 / odds["away"]
        total_imp = imp_home + imp_draw + imp_away
        imp_home /= total_imp
        imp_draw /= total_imp
        imp_away /= total_imp
        raw["odds_implied"] = f"主{imp_home:.0%} 平{imp_draw:.0%} 客{imp_away:.0%}"

        if imp_home > imp_away:
            advantage = min((imp_home - imp_away) * 10, 4)
            scores["home"]["odds_market"] = min(5 + advantage, 9)
            scores["away"]["odds_market"] = max(5 - advantage, 1)
        elif imp_away > imp_home:
            advantage = min((imp_away - imp_home) * 10, 4)
            scores["home"]["odds_market"] = max(5 - advantage, 1)
            scores["away"]["odds_market"] = min(5 + advantage, 9)
        else:
            scores["home"]["odds_market"] = 5
            scores["away"]["odds_market"] = 5
    else:
        scores["home"]["odds_market"] = DEFAULT_SCORE
        scores["away"]["odds_market"] = DEFAULT_SCORE
        raw["odds_implied"] = "无赔率数据"

    return {"scores": scores, "bonus": bonus, "raw": raw}


# ============================================================
# 加权总分
# ============================================================

def compute_weighted_total(dim_scores):
    scores = dim_scores["scores"]
    total_h = sum(scores["home"].get(dim, DEFAULT_SCORE) * w
                  for dim, w in WEIGHTS.items())
    total_a = sum(scores["away"].get(dim, DEFAULT_SCORE) * w
                  for dim, w in WEIGHTS.items())
    return total_h, total_a


# ============================================================
# 概率计算（修正版：保证归一化）
# ============================================================

def compute_probabilities(score_home, score_away, stage="GROUP_STAGE"):
    """
    输入：主客加权总分、赛事阶段
    输出：[主胜概率, 平局概率, 客胜概率]（保证和为1.0）
    """
    # 1. 预期进球比
    goal_ratio = (score_home / max(score_away, 0.1)) ** GOAL_RATIO_SMOOTH

    # 2. 概率初值
    prob_home = goal_ratio / (1 + goal_ratio) * HOME_AWAY_SPLIT
    prob_away = (1.0 / (1 + goal_ratio)) * HOME_AWAY_SPLIT
    prob_draw = 1.0 - prob_home - prob_away

    # 3. 淘汰赛平局修正
    is_knockout = "KNOCKOUT" in stage.upper() or "淘汰" in stage
    if is_knockout:
        prob_draw = min(prob_draw * KNOCKOUT_DRAW_BOOST, MAX_DRAW_PROB)
        remaining = 1.0 - prob_draw
        if (prob_home + prob_away) > 0:
            prob_home = prob_home / (prob_home + prob_away) * remaining
            prob_away = remaining - prob_home
        else:
            prob_home = remaining / 2
            prob_away = remaining / 2

    # 4. 边界保护
    prob_draw = max(prob_draw, MIN_DRAW_PROB)
    prob_home = max(prob_home, 0.05)
    prob_away = max(prob_away, 0.05)

    # 5. 强制归一化（修正原始设计的bug）
    total = prob_home + prob_draw + prob_away
    prob_home /= total
    prob_draw /= total
    prob_away /= total

    return [prob_home, prob_draw, prob_away]


# ============================================================
# 风险评级
# ============================================================

def assess_risk(probs, scores, odds):
    """
    判定风险等级。
    """
    max_prob = max(probs)
    draw_prob = probs[1]
    injury_h = scores["home"].get("injuries", DEFAULT_SCORE)
    injury_a = scores["away"].get("injuries", DEFAULT_SCORE)
    min_injury = min(injury_h, injury_a)

    # 赔率倒挂判定：赔率隐含概率最大方向 ≠ 模型预测最大方向
    odds_inverted = False
    if odds:
        imp_home = 1.0 / odds["home"]
        imp_draw = 1.0 / odds["draw"]
        imp_away = 1.0 / odds["away"]
        imp_total = imp_home + imp_draw + imp_away
        imp_probs = [imp_home / imp_total, imp_draw / imp_total, imp_away / imp_total]
        model_dir = probs.index(max_prob)
        odds_dir = imp_probs.index(max(imp_probs))
        if model_dir != odds_dir:
            odds_inverted = True

    # 低风险
    if (max_prob >= RISK_THRESHOLDS["low"]["min_max_prob"]
            and min_injury >= RISK_THRESHOLDS["low"]["min_injury_score"]
            and not odds_inverted):
        return "低风险"

    # 中风险
    lo, hi = RISK_THRESHOLDS["medium"]["max_prob_range"]
    if (lo <= max_prob <= hi) or (draw_prob >= RISK_THRESHOLDS["medium"]["high_draw_threshold"]):
        return "中风险"

    return "高风险"


# ============================================================
# 购彩方案生成
# ============================================================

def generate_proposal(probs, risk_level):
    max_prob = max(probs)
    max_idx = probs.index(max_prob)
    labels = ["主胜", "平局", "客胜"]

    if risk_level == "低风险" and max_prob >= 0.65:
        return {
            "tier": "小额娱乐档",
            "amount": "10-30元",
            "suggestion": f"单关 {labels[max_idx]}",
            "oneliner": "稳胆局，不建议防冷",
            "warnings": [],
        }
    elif risk_level == "低风险":
        return {
            "tier": "稳健尝试档",
            "amount": "30-80元",
            "suggestion": f"2串1（主推{labels[max_idx]} + 另一场低风险选项）",
            "oneliner": "可做胆，但建议串关分散",
            "warnings": [],
        }
    elif risk_level == "中风险" and probs[1] >= 0.30:
        direction = "胜+平" if probs[0] > probs[2] else "平+负"
        return {
            "tier": "博取档",
            "amount": "20-50元",
            "suggestion": f"双选 {direction}",
            "oneliner": "胶着局，可小搏平局",
            "warnings": ["不推荐单关高赔"],
        }
    elif risk_level == "中风险":
        return {
            "tier": "谨慎档",
            "amount": "10-30元",
            "suggestion": f"单关 {labels[max_idx]}（小注）",
            "oneliner": "数据信号不明确，小注试探",
            "warnings": [],
        }
    else:
        return {
            "tier": "不建议投入",
            "amount": f"<= {MAX_HIGH_RISK_AMOUNT}元",
            "suggestion": f"娱乐单关（{MAX_HIGH_RISK_AMOUNT}元以内）",
            "oneliner": "冷门概率高，数据异常，谨慎",
            "warnings": ["冷门概率高 数据异常 谨慎"],
        }


# ============================================================
# 一句话结论
# ============================================================

def generate_oneliner(data, probs, scores, dim_scores, risk_level):
    home = data["home"]
    away = data["away"]
    max_idx = probs.index(max(probs))
    labels = ["主胜", "平局", "客胜"]
    result_label = labels[max_idx]

    dim_labels = {
        "team_strength": "硬实力",
        "recent_form": "近期状态",
        "injuries": "伤停",
        "head_to_head": "交锋",
        "external": "场外",
        "odds_market": "赔率",
    }

    parts = []
    for dim, label in dim_labels.items():
        sh = scores["home"].get(dim, DEFAULT_SCORE)
        sa = scores["away"].get(dim, DEFAULT_SCORE)
        diff = sh - sa
        if abs(diff) >= 3:
            side = home if diff > 0 else away
            parts.append(f"{side}{label}占优")

    if risk_level == "高风险":
        return f"{home} vs {away} — 数据矛盾严重，不宜重注"
    elif risk_level == "中风险" and probs[1] >= 0.30:
        return f"{home} vs {away} — 胶着局，大概率平局或一球胜负，倾向{result_label}"
    elif parts:
        return f"{home} vs {away} — {'、'.join(parts[:2])}，倾向{result_label}"
    else:
        return f"{home} vs {away} — 综合数据倾向{result_label}（概率{probs[max_idx]:.0%}）"


# ============================================================
# 完整分析流程（单场）
# ============================================================

def analyze_match(data):
    home = data["home"]
    away = data["away"]
    match = data["match"]

    dim_result = compute_dimension_scores(data)
    scores = dim_result["scores"]
    raw_info = dim_result["raw"]

    total_h, total_a = compute_weighted_total(dim_result)
    raw_info["total_home"] = total_h
    raw_info["total_away"] = total_a

    stage = match.get("stage", "GROUP_STAGE")
    probs = compute_probabilities(total_h, total_a, stage)

    risk = assess_risk(probs, scores, data.get("odds"))

    proposal = generate_proposal(probs, risk)

    oneliner = generate_oneliner(data, probs, scores, dim_result, risk)

    return {
        "match": match,
        "home": home,
        "away": away,
        "data_status": data.get("data_status", {}),
        "dimension_scores": {
            "home": dict(scores["home"]),
            "away": dict(scores["away"]),
        },
        "raw": raw_info,
        "total_scores": {"home": round(total_h, 2), "away": round(total_a, 2)},
        "probabilities": {
            "home_win": round(probs[0], 4),
            "draw": round(probs[1], 4),
            "away_win": round(probs[2], 4),
        },
        "risk_level": risk,
        "proposal": proposal,
        "oneliner": oneliner,
        "analyzed_at": datetime.now().isoformat(),
    }
