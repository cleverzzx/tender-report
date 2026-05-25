# -*- coding: utf-8 -*-
"""数据持久化模块 —— 标讯缓存，用于补全字段和标记新标讯 v3.3"""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.models import DetectionStats, Tender, TenderField

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
CACHE_FILE = DATA_DIR / "tender_cache.json"


def _tender_hash(tender: Tender) -> str:
    """生成标讯唯一标识哈希（标题+招标编号）。"""
    tn = tender.get_field_value("招标编号") or ""
    key = f"{tender.title}|{tn}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


def _field_to_dict(field: TenderField) -> Dict[str, str]:
    return {"name": field.name, "value": field.value}


def _tender_to_cache_entry(tender: Tender) -> Dict[str, Any]:
    """将标讯关键字段序列化为缓存条目。"""
    return {
        "title": tender.title,
        "key": tender.key,
        "special": tender.special,
        "fields": [_field_to_dict(f) for f in tender.fields],
        "first_seen": datetime.now().isoformat(),
        "last_seen": datetime.now().isoformat(),
        "source": tender._source,
        "url": tender._url,
    }


def _merge_field_from_cache(tender: Tender, cache_entry: Dict[str, Any]) -> int:
    """将缓存中的字段补充到当前标讯（仅补充当前缺失的字段）。

    返回补充的字段数。
    """
    cache_fields: List[Dict[str, str]] = cache_entry.get("fields", [])
    existing_names = {f.name for f in tender.fields}
    added = 0

    # 需要补全的关键字段（按优先级排列）
    priority_fields = [
        "截止日期", "投标截止日期", "Deadline", "Closing Date",
        "标书价格", "投标文件价格(USD)", "合同金额",
        "投标保证金", "履约保证金", "保证金",
        "采购方式", "投标有效期", "投标资格",
        "联系人", "项目名称", "标书发售截止", "开标日期",
        "标书可获取日期", "合同期",
        "备 注", "职位", "地址", "电话", "邮箱",
    ]

    for pf in priority_fields:
        if pf in existing_names:
            continue
        for cf in cache_fields:
            if cf["name"] == pf and cf["value"]:
                tender.fields.append(TenderField(name=pf, value=cf["value"]))
                existing_names.add(pf)
                added += 1
                break

    return added


def load_cache() -> Dict[str, Any]:
    """加载缓存。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not CACHE_FILE.exists():
        return {"version": 2, "tenders": {}}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"缓存文件读取失败: {e}")
        return {"version": 2, "tenders": {}}


def save_cache(cache: Dict[str, Any]) -> None:
    """保存缓存。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.error(f"缓存保存失败: {e}")


def enrich_and_mark_new(
    tenders: Dict[str, List[Tender]],
) -> Tuple[Dict[str, List[Tender]], int, DetectionStats]:
    """对比缓存：补全缺失字段 + 标记新标讯。

    每次都会重新爬取，缓存仅用于：
    1. 补充当前爬取未能提取到的字段（如之前OCR成功的截止日期）
    2. 标记首次出现的标讯为 [NEW]

    Args:
        tenders: 当前爬取+合并后的标讯 {"BAPEX": [...], ...}

    Returns:
        (补全后的标讯, 新标讯数量, 统计信息)
    """
    cache = load_cache()
    cache_tenders: Dict[str, Any] = cache.get("tenders", {})
    new_count = 0
    total = 0
    enriched = 0

    for company, tlist in tenders.items():
        for tender in tlist:
            total += 1
            h = _tender_hash(tender)
            cache_entry = cache_tenders.get(h)

            if cache_entry is None:
                # 首次出现 → 标记为 [NEW]
                tender._is_new = True
                new_count += 1
                # 写入缓存
                cache_tenders[h] = _tender_to_cache_entry(tender)
            else:
                # 已见过 → 补全缺失字段 + 更新 last_seen
                tender._is_new = False
                n = _merge_field_from_cache(tender, cache_entry)
                if n > 0:
                    enriched += n
                # 如果当前数据更丰富，更新缓存
                if len(tender.fields) > len(cache_entry.get("fields", [])):
                    cache_tenders[h] = _tender_to_cache_entry(tender)
                else:
                    cache_tenders[h]["last_seen"] = datetime.now().isoformat()

    cache["tenders"] = cache_tenders
    save_cache(cache)

    if new_count > 0:
        print(f"      ✓ 发现 {new_count} 条新增标讯 [NEW]")
        logger.info(f"发现 {new_count} 条新增标讯")
    if enriched > 0:
        print(f"      ✓ 从缓存补全 {enriched} 个缺失字段")
        logger.info(f"从缓存补全 {enriched} 个缺失字段")

    stats = DetectionStats(total=total, new=new_count, by_company={})
    for company, tlist in tenders.items():
        stats.by_company[company] = {
            "total": len(tlist),
            "new": sum(1 for t in tlist if t._is_new),
        }

    return tenders, new_count, stats


# 兼容旧版 API
def detect_new_tenders(
    current_tenders: Dict[str, List[Tender]],
) -> Tuple[Dict[str, List[Tender]], int, DetectionStats]:
    """检测新增标讯并补全字段（兼容旧版 API）。"""
    return enrich_and_mark_new(current_tenders)


def get_last_run_time() -> Optional[datetime]:
    """获取上次运行时间。"""
    cache = load_cache()
    # 找最近的 last_seen
    latest = None
    for entry in cache.get("tenders", {}).values():
        ls = entry.get("last_seen", "")
        if ls:
            try:
                dt = datetime.fromisoformat(ls)
                if latest is None or dt > latest:
                    latest = dt
            except ValueError:
                pass
    return latest


def clear_cache() -> None:
    """清空缓存。"""
    if CACHE_FILE.exists():
        try:
            CACHE_FILE.unlink()
            logger.info("缓存已清空")
        except IOError as e:
            logger.error(f"清空缓存失败: {e}")
