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
from datetime import datetime, timedelta, timezone

# Add parent scripts dir to path so imports work from cron
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    LOG_DIR, DISCLAIMER,
)
from fetch_data import fetch_schedule, collect_match_data
from analyze import analyze_match
from output import format_console_report, format_compact_report, save_results

BEIJING_TZ = timezone(timedelta(hours=8))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "analysis.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("main")


def _utc_to_beijing(utc_str):
    """UTC 时间 → 北京时间日期"""
    try:
        s = utc_str.replace("Z", "+00:00")
        return datetime.fromisoformat(s).astimezone(BEIJING_TZ)
    except Exception:
        return None


def run_analysis(date_str=None, match_filter=None):
    """
    主流程。date_str 为北京时间日期 (YYYY-MM-DD)。
    自动查询对应 UTC 日期范围，筛选出北京时间当天的比赛。
    """
    if date_str is None:
        date_str = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d")

    log.info(f"开始分析: 北京日期={date_str}, filter={match_filter}")

    # 北京时间一天对应 UTC 范围：
    # 北京 6/14 00:00 = UTC 6/13 16:00
    # 北京 6/15 00:00 = UTC 6/14 16:00
    # 所以查 UTC 6/13 和 6/14 两天，再筛选北京日期
    bj_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=BEIJING_TZ)
    utc_start = (bj_date - timedelta(hours=8)).strftime("%Y-%m-%d")
    utc_end = (bj_date + timedelta(hours=16)).strftime("%Y-%m-%d")

    # 1. 获取赛程（查询跨两天的 UTC 日期）
    all_matches = []
    for d in [utc_start, utc_end]:
        matches = fetch_schedule(d)
        all_matches.extend(matches)

    # 去重
    seen = set()
    unique = []
    for m in all_matches:
        mid = m.get("match_id", f"{m['home']}-{m['away']}")
        if mid not in seen:
            seen.add(mid)
            unique.append(m)

    # 筛选北京时间当天的比赛
    matches = []
    for m in unique:
        bj_time = _utc_to_beijing(m.get("kickoff", ""))
        if bj_time and bj_time.strftime("%Y-%m-%d") == date_str:
            matches.append(m)

    if not matches:
        msg = f"北京时间 {date_str} 无世界杯比赛"
        log.info(msg)
        return [], f"{msg}。", f"⚽ 北京时间{date_str}无世界杯比赛\n\n--- {DISCLAIMER}"

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

    date_str = args.date or datetime.now(BEIJING_TZ).strftime("%Y-%m-%d")
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
