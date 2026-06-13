"""
世界杯足彩分析工具 — 集中配置
所有权重、阈值、查表映射都在这里，方便调参。
"""

import os
from pathlib import Path

# ============================================================
# 加载 .env 文件（优先级最低，环境变量会覆盖）
# ============================================================
SKILL_DIR = Path(__file__).resolve().parent.parent  # skill root

def _load_dotenv():
    """加载 skill 根目录的 .env 文件"""
    env_path = SKILL_DIR / ".env"
    if not env_path.exists():
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip('"').strip("'")
            if key and key not in os.environ:  # 不覆盖已有环境变量
                os.environ[key] = val

_load_dotenv()

# ============================================================
# 路径配置
# ============================================================
TEMPLATES_DIR = SKILL_DIR / "templates"
DATA_DIR = Path(os.environ.get("WC_DATA_DIR", SKILL_DIR / "data"))
RAW_DIR = DATA_DIR / "raw"
ANALYSIS_DIR = DATA_DIR / "analysis"
REVIEW_DIR = DATA_DIR / "review"
LOG_DIR = DATA_DIR / "logs"

for d in [DATA_DIR, RAW_DIR, ANALYSIS_DIR, REVIEW_DIR, LOG_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ============================================================
# API 密钥（优先级：环境变量 > .env文件 > 空字符串）
# ============================================================
FOOTBALL_DATA_API_KEY = os.environ.get("FOOTBALL_DATA_API_KEY", "")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")

# ============================================================
# 六维度权重（总和 = 1.0）
# ============================================================
WEIGHTS = {
    "team_strength": 0.20,   # 球队硬实力：FIFA排名 + 身价
    "recent_form":   0.20,   # 近期竞技状态：近5场积分
    "injuries":      0.15,   # 核心伤停（降权，数据不可靠）
    "head_to_head":  0.10,   # 历史交锋
    "external":      0.10,   # 场外环境：气候/主场/战意
    "odds_market":   0.25,   # 赔率市场倾向（提权，最有效信号）
}

# ============================================================
# 查表映射：原始值 → 0-10 得分
# ============================================================

# 核心伤停人数 → 得分
INJURY_SCORE = {
    "0": 10,
    "1": 6,
    "2": 3,
    "3+": 2,
}

# 近5场积分 → 得分
FORM_SCORE = [
    (13, 9),   # >=13 分 → 9
    (10, 7),   # >=10 分 → 7
    (7,  5),   # >=7 分 → 5
    (0,  4),   # 兜底 → 4
]

# FIFA 排名差 (abs) → 实力得分
RANK_GAP_SCORE = [
    (5,  9),   # 差距 ≤5  → 9分
    (15, 7),   # 差距 ≤15 → 7分
    (30, 5),   # 差距 ≤30 → 5分
    (float("inf"), 3),  # 差距 >30 → 3分
]

# 历史交锋胜率 → 得分
H2H_SCORE = [
    (0.60, 8),  # ≥60% → 8
    (0.40, 5),  # ≥40% → 5
    (0.0,  3),  # <40% → 3
]

# 场外因素微调
EXTERNAL_BONUS = {
    "host":         1,    # 东道主
    "no_travel":    1,    # 无长途飞行
    "long_travel": -1,    # 长途飞行
    "high_temp":   -1,    # 高温
    "neutral":      0,
}

# ============================================================
# 赔率维度：竞彩赔率 → 隐含概率 → 偏离度 → 得分
# ============================================================
# 当模型概率与赔率隐含概率一致 → 7分（中性偏正）
# 当赔率更看好模型预测方向 → 9分（市场印证）
# 当赔率与模型预测相反（倒挂）→ 3分（市场警示）
ODDS_ALIGNMENT_SCORE = {
    "strong_agree": 9,   # 偏离 ≤5% 且方向一致
    "agree":        7,   # 偏离 5-15% 方向一致
    "neutral":      5,   # 偏离 15-25%
    "disagree":     3,   # 偏离 >25% 方向一致（过热）
    "inverted":     2,   # 方向相反（倒挂）
}

# ============================================================
# 概率计算参数
# ============================================================
GOAL_RATIO_SMOOTH = 0.8    # 预期进球比平滑指数
HOME_AWAY_SPLIT = 0.7      # 初始主客胜分配比例
MIN_DRAW_PROB = 0.15       # 平局最低概率
KNOCKOUT_DRAW_BOOST = 1.2  # 淘汰赛平局修正系数
MAX_DRAW_PROB = 0.45       # 平局概率上限

# ============================================================
# 风险评级阈值
# ============================================================
RISK_THRESHOLDS = {
    "low": {
        "min_max_prob": 0.60,      # 单一结果概率 ≥ 此值
        "min_injury_score": 6,     # 伤停得分 ≥ 此值
        "no_inversion": True,      # 赔率不倒挂
    },
    "medium": {
        "max_prob_range": (0.40, 0.60),  # 最大概率在此区间
        "high_draw_threshold": 0.30,     # 平局概率 ≥ 此值
    },
    # 其余为高风险
}

# ============================================================
# 购彩方案规则
# ============================================================
MAX_HIGH_RISK_AMOUNT = 10     # 高风险上限（元）
MAX_MEDIUM_RISK_AMOUNT = 50   # 中风险上限
MAX_LOW_RISK_AMOUNT = 100     # 低风险上限
NEVER_RECOMMEND_COMBO = 4     # 永不推荐 ≥4串1

# ============================================================
# 默认值（数据缺失时使用）
# ============================================================
DEFAULT_SCORE = 5             # 中性分
DEFAULT_H2H_WINRATE = 0.50   # 默认五五开
DEFAULT_RANK_GAP = 10        # 默认排名差（中等）
DEFAULT_RECENT_POINTS = 7    # 默认近5场积分
DEFAULT_INJURY_COUNT = 0     # 默认无伤停

# ============================================================
# 赛事信息
# ============================================================
TOURNAMENT = "2026世界杯"
TIMEZONE = "Asia/Shanghai"

# Feishu 推送配置
FEISHU_TARGET = "feishu:oc_294ad292bc5583954460b62ab9579bc4"

# 输出免责声明
DISCLAIMER = "体彩为娱乐，非投资，概率仅供参考"
