#!/usr/bin/env python3
"""
世界杯足彩自动化分析工具 — 主入口

用法:
    python main.py                    分析今日比赛
    python main.py --date 2026-06-15  分析指定日期
    python main.py --match "法国-阿根廷"  分析指定比赛
    python main.py --verbose          详细输出
    python main.py --compact          紧凑输出（适合推送）
    python main.py --feishu           发送到飞书
"""

import sys
import os

# ---- 修复 Windows PYTHONHOME 冲突 ----
# 如果 PYTHONHOME 指向了损坏的 uv Python，清除它以使用正确的 Python
_pyhome = os.environ.get("PYTHONHOME", "")
if "uv" in _pyhome.lower() or "cpython-3.11" in _pyhome:
    os.environ.pop("PYTHONHOME", None)
    os.environ.pop("UV_INTERNAL__PYTHONHOME", None)

import argparse
import logging
from datetime import datetime

# Add parent scripts dir to path so imports work from cron
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    LOG_DIR, DISCLAIMER, FEISHU_TARGET,
)
from fetch_data import fetch_schedule, collect_match_data
from analyze import analyze_match
from output import format_console_report, format_compact_report, save_results

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "analysis.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("main")


def run_analysis(date_str=None, match_filter=None):
    """
    主流程：赛程 → 采集 → 分析 → 输出
    返回: (results_list, console_output, compact_output)
    """
    log.info(f"开始分析: date={date_str}, filter={match_filter}")

    # 1. 获取赛程
    matches = fetch_schedule(date_str)
    if not matches:
        msg = f"日期 {date_str} 无世界杯比赛"
        log.info(msg)
        return [], f"{msg}。", f"⚽ 今日无世界杯比赛\n\n--- {DISCLAIMER}"

    # 2. 过滤
    if match_filter:
        matches = [m for m in matches
                   if match_filter in f"{m['home']}-{m['away']}"
                   or match_filter in f"{m['home']}{m['away']}"]
        if not matches:
            msg = f"未找到比赛: {match_filter}"
            log.warning(msg)
            return [], msg, msg

    log.info(f"找到 {len(matches)} 场比赛: {[m['home']+' vs '+m['away'] for m in matches]}")

    # 3. 逐场采集 + 分析
    results = []
    for match in matches:
        data = collect_match_data(match)
        result = analyze_match(data)
        results.append(result)
        log.info(f"分析完成: {match['home']} vs {match['away']} — {result['risk_level']}")

    # 4. 格式化
    console_out = format_console_report(results)
    compact_out = format_compact_report(results)

    # 5. 持久化
    json_p, csv_p = save_results(results)
    log.info(f"结果已保存: {json_p}, {csv_p}")

    return results, console_out, compact_out


def main():
    parser = argparse.ArgumentParser(description="世界杯足彩自动化分析工具")
    parser.add_argument("--date", default=None, help="分析日期 YYYY-MM-DD (默认今天)")
    parser.add_argument("--match", default=None, help="过滤特定比赛 (如 '法国-阿根廷')")
    parser.add_argument("--verbose", action="store_true", help="详细输出")
    parser.add_argument("--compact", action="store_true", help="紧凑输出")
    parser.add_argument("--feishu", action="store_true", help="发送到飞书")

    args = parser.parse_args()

    date_str = args.date or datetime.now().strftime("%Y-%m-%d")
    results, console_out, compact_out = run_analysis(date_str, args.match)

    # 输出
    if args.compact:
        print(compact_out)
    elif args.verbose:
        print(console_out)
        print(f"\n数据状态详情:")
        for r in results:
            ds = r.get("data_status", {})
            raw = r.get("raw", {})
            print(f"  {r['home']} vs {r['away']}:")
            print(f"    数据: {ds}")
            print(f"    原始: {raw}")
    else:
        print(console_out)

    # 飞书推送
    if args.feishu and results:
        # 使用 Hermes send_message 需要特殊处理：这里只输出 compact 格式
        # 由 cron job 或外部脚本调用 send_message
        print("\n[飞书推送内容]")
        print(compact_out)

    return 0 if results else 1


if __name__ == "__main__":
    sys.exit(main())
