# 世界杯足彩分析工具 — 数据维护手册 (v3 MCP 全自动版)

## 自动化程度总览

| 数据维度 | 权重 | 方式 | 说明 |
|----------|------|------|------|
| 赛程 | — | ✅ 全自动 | Football-Data.org API |
| 赔率 | 25% | ✅ 全自动 | The Odds API + CSV 兜底 |
| FIFA排名 | 20% | ✅ 全自动 | WC26 MCP `get_teams` |
| 近期状态 | 20% | ✅ 全自动 | WC 完赛场次自动计分 |
| 伤停 | 15% | ✅ 全自动 | WC26 MCP `get_injuries` |
| 历史交锋 | 10% | ✅ 全自动 | WC 历史场次 + MCP `get_historical_matchups` |

# 世界杯足彩分析工具 — 数据维护手册 (v3 全自动版)

## ⚡ 当前状态：零手动维护

所有数据源已自动化。CSV 模板仅作为离线兜底。

## 自动化覆盖

| 数据 | 来源 | 需要手动？ |
|------|------|-----------|
| 赛程 | Football-Data.org API | ❌ |
| 赔率 | The Odds API | ❌ |
| FIFA排名 | WC26 MCP `get_teams` (48队) | ❌ |
| 伤停 | WC26 MCP `get_injuries` (18条/15队) | ❌ |
| 近期状态 | WC 完赛场次自动计分 | ❌ |
| 历史交锋 | WC 完赛场次自动统计 | ❌ |

## CSV 兜底（仅 API/MCP 全部挂掉时才需要）

```
world-cup-betting-analysis/
├── .env                  ← API Key 配置
├── scripts/              ← 代码（不用动）
├── templates/            ← CSV 模板（仅兜底，日常不填）
│   ├── injuries.csv      MCP get_injuries 兜底
│   ├── odds.csv          Odds API 兜底
│   ├── fifa_ranking.csv  MCP get_teams 兜底
│   ├── recent_form.csv   WC 赛事兜底
│   ├── h2h.csv           WC 赛事兜底
│   └── schedule.csv      Football-Data.org 兜底
└── data/                 ← 自动生成的分析结果
```

---

## 数据来源详细说明

### WC26 MCP 服务器

```
npm 包: wc26-mcp v0.3.1
安装:   npm install -g wc26-mcp
工具数: 18 个
位置:   ~/AppData/Roaming/npm/wc26-mcp.cmd
```

| MCP 工具 | 提供的数据 | 覆盖范围 |
|----------|-----------|----------|
| `get_teams` | FIFA 排名、分组、国旗 | 48 支球队全部 |
| `get_injuries` | 核心球员伤停 | 18 条、15 支球队（豪门为主） |
| `get_historical_matchups` | 历史交锋记录 | 全量 |
| `get_team_profile` | 教练、核心球员、打法 | 48 支球队 |
| `compare_teams` | 两两对比 | 任意两队 |
| `get_venues` | 16 个场馆详情 | 全量 |

> 注意：MCP `get_injuries` 对豪门球队（法国、阿根廷、巴西等）有数据，
> 对加拿大、波黑等小球队返回空。系统自动 fallback 到 CSV 或默认值。

### 其他 API

| API | 用途 | 请求数限制 |
|-----|------|-----------|
| Football-Data.org | 赛程、完赛比分 | 10 req/min（免费 tier） |
| The Odds API | 比赛赔率 | 500 req/month（免费 tier） |

---

## 快速测试

```bash
cd ~/AppData/Local/hermes/skills/data-science/world-cup-betting-analysis/scripts
python main.py                    # 今日比赛
python main.py --date 2026-06-16  # 指定日期
python main.py --verbose          # 详细输出
python main.py --compact          # 紧凑版（适合推送）
```
