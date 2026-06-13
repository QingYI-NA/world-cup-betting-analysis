# 世界杯足彩自动化分析工具

基于多源数据（WC26 MCP + The Odds API + Football-Data.org）的六维度打分模型，自动生成每日比赛预测和分层购彩方案。

## 数据源

| 维度 | 权重 | 来源 |
|------|------|------|
| 赔率市场 | 25% | The Odds API |
| 硬实力 | 20% | WC26 MCP (FIFA排名) |
| 近期状态 | 20% | Football-Data.org (赛事计分) |
| 核心伤停 | 15% | WC26 MCP (get_injuries) |
| 历史交锋 | 10% | Football-Data.org / WC26 MCP |
| 场外环境 | 10% | 默认中性(可手动调整) |

## 前置依赖

```bash
# Python 3.9+
pip install requests

# WC26 MCP 服务器（伤停 + FIFA排名数据）
npm install -g wc26-mcp
```

## 配置

```bash
# 复制 .env 模板并填入 API Key
cp .env.example .env
```

`.env` 内容：
```
FOOTBALL_DATA_API_KEY=你的key    # https://www.football-data.org/
ODDS_API_KEY=你的key             # https://the-odds-api.com/
```

## 使用

```bash
cd scripts
python main.py                     # 今天所有比赛
python main.py --date 2026-06-15   # 指定日期
python main.py --compact           # 紧凑模式(适合推送)
python main.py --verbose           # 详细模式
```

## 输出示例

```
⚽ 2026世界杯 每日分析
06-12 18:30 北京时间

🟡 Canada vs Bosnia-Herzegovina
   ⏰ 06-13 03:00 北京时间
   📊 主39% 平30% 客31%
   💬 加拿大主场+排名优势，小注主胜或防平
   🥉 小额娱乐: 单关 主胜 (10-30元)
   🥈 稳健尝试: 双选 胜+平 (20-50元)
   🥇 博高赔: 搏冷门 客胜 (10-20元)
```

## 手动数据维护（可选）

CSV 模板在 `templates/` 目录，API 不可用时手动填写：
- `schedule.csv` — 赛程
- `injuries.csv` — 伤停（MCP 已覆盖大部分）
- `odds.csv` — 赔率兜底
- `fifa_ranking.csv` — FIFA排名兜底
- `recent_form.csv` — 近期状态兜底
- `h2h.csv` — 历史交锋兜底

详见 `references/MAINTENANCE.md`

## 免责声明

体彩为娱乐，非投资，概率仅供参考。
