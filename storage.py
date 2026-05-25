# -*- coding: utf-8 -*-
"""数据管理模块 —— 每次重新爬取，不保留历史缓存"""

from datetime import datetime


def detect_new_tenders(current_tenders):
    """
    检测标讯（每次重新爬取，不保留历史缓存）。

    Args:
        current_tenders: 当前获取的标讯字典 {"BAPEX": [...], "BGFCL": [...], ...}

    Returns:
        (merged_tenders, new_count, stats)
    """
    merged = {}
    stats = {"total": 0, "new": 0, "by_company": {}}

    for company, tenders in current_tenders.items():
        merged[company] = []

        for tender in tenders:
            stats["total"] += 1
            tender["_is_new"] = True
            tender["_hash"] = ""
            merged[company].append(tender)

        stats["by_company"][company] = {
            "total": len(tenders),
            "new": len(tenders),
        }

    stats["new"] = stats["total"]

    return merged, stats["total"], stats


def get_last_run_time():
    """获取上次运行时间（无缓存模式，返回None）。"""
    return None
