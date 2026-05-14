# -*- coding: utf-8 -*-
"""数据持久化模块 —— 历史标讯存储与新标讯检测"""

import json
import hashlib
import os
from datetime import datetime
from pathlib import Path

DATA_DIR = Path("data")
HISTORY_FILE = DATA_DIR / "tender_history.json"


def _ensure_data_dir():
    """确保数据目录存在。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _tender_hash(tender):
    """生成标讯的唯一标识哈希。"""
    # 使用标题和招标编号作为唯一标识
    key = f"{tender.get('title', '')}|{tender.get('fields', [])[0][1] if tender.get('fields') else ''}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


def load_history():
    """加载历史标讯数据。"""
    _ensure_data_dir()
    if not HISTORY_FILE.exists():
        return {"version": 1, "last_run": None, "tenders": {}}

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"version": 1, "last_run": None, "tenders": {}}


def save_history(history):
    """保存历史标讯数据。"""
    _ensure_data_dir()
    history["last_run"] = datetime.now().isoformat()
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def detect_new_tenders(current_tenders):
    """
    检测新增标讯。

    Args:
        current_tenders: 当前获取的标讯字典 {"BAPEX": [...], "BGFCL": [...], ...}

    Returns:
        (merged_tenders, new_count, stats)
    """
    history = load_history()
    known_hashes = set(history.get("tenders", {}).keys())

    merged = {}
    new_count = 0
    stats = {"total": 0, "new": 0, "by_company": {}}

    new_hashes = {}

    for company, tenders in current_tenders.items():
        merged[company] = []
        company_new = 0

        for tender in tenders:
            tender_hash = _tender_hash(tender)
            stats["total"] += 1

            # 标记是否为新标讯
            is_new = tender_hash not in known_hashes
            tender["_is_new"] = is_new
            tender["_hash"] = tender_hash

            if is_new:
                new_count += 1
                company_new += 1

            merged[company].append(tender)
            new_hashes[tender_hash] = {
                "title": tender.get("title", "")[:80],
                "company": company,
                "first_seen": datetime.now().isoformat(),
            }

        stats["by_company"][company] = {
            "total": len(tenders),
            "new": company_new,
        }

    stats["new"] = new_count

    # 保存更新后的历史
    history["tenders"].update(new_hashes)
    save_history(history)

    return merged, new_count, stats


def get_last_run_time():
    """获取上次运行时间。"""
    history = load_history()
    last_run = history.get("last_run")
    if last_run:
        try:
            return datetime.fromisoformat(last_run)
        except ValueError:
            pass
    return None


def clear_history():
    """清空历史数据。"""
    if HISTORY_FILE.exists():
        HISTORY_FILE.unlink()
