# -*- coding: utf-8 -*-
"""数据管理模块 —— 标讯数据获取与合并"""

import difflib
import logging
from typing import Dict, List, Optional, Tuple

from config import get_fallback_tenders
from src.models import DetectionStats, ScrapedEntry, Tender, TenderField
from src.scraper import scrape_all_listings
from src.storage import detect_new_tenders

logger = logging.getLogger(__name__)


def _normalize_scraped_entry(entry: ScrapedEntry, company: Optional[str] = None) -> Tender:
    """将爬取的原始条目转换为标准标讯格式。

    Args:
        entry: 爬取到的原始条目
        company: 公司名称（可选）

    Returns:
        标准化 Tender 对象
    """
    # 从标题推断公司（如果未指定）
    if not company:
        title_lower = entry.title.lower()
        if "bapex" in title_lower:
            company = "BAPEX"
        elif "bgfcl" in title_lower:
            company = "BGFCL"
        elif "sgfl" in title_lower:
            company = "SGFL"

    fields = [
        TenderField("招标编号", "未知（请查看详情页）"),
        TenderField("发布日期", entry.date_text or "详见详情页"),
        TenderField("采购内容", entry.title),
        TenderField(
            "官方来源",
            f"<a href='{entry.url}' color='blue'>点击查看详情页</a>" if entry.url else "未提供",
        ),
    ]

    return Tender(
        title=entry.title,
        key=f"状态: <b>新爬取</b> | 来源: {company or 'Unknown'}",
        special="<b>从官网爬取</b> | 请访问详情页获取完整信息",
        fields=fields,
        _source="scraped",
        _url=entry.url,
    )


def _merge_tenders(
    fallback_tenders: Dict[str, List[Tender]],
    scraped_listings: Dict[str, List[ScrapedEntry]],
    similarity_threshold: float = 0.75,
) -> Dict[str, List[Tender]]:
    """合并 fallback 数据和爬取数据，去重并标记来源。

    去重策略：
    - 以标题相似度为主要判断依据
    - 如果爬取的标题与 fallback 中某条标题相似度>threshold，认为是同一条

    Args:
        fallback_tenders: fallback 标讯数据
        scraped_listings: 爬取到的标讯列表
        similarity_threshold: 相似度阈值（默认 0.75）

    Returns:
        合并后的标讯字典
    """
    merged: Dict[str, List[Tender]] = {}

    for company in ["BAPEX", "BGFCL", "SGFL"]:
        company_tenders = fallback_tenders.get(company, []).copy()
        company_scraped = scraped_listings.get(company, [])

        # 如果没有爬取到数据，直接使用 fallback
        if not company_scraped:
            merged[company] = company_tenders
            continue

        # 获取已存在的标题列表用于去重
        existing_titles = [t.title.lower() for t in company_tenders]

        added_count = 0
        for entry in company_scraped:
            entry_title = entry.title.lower()
            if not entry_title or len(entry_title) < 10:
                continue

            # 检查是否与现有标题相似
            is_duplicate = False
            for existing in existing_titles:
                similarity = difflib.SequenceMatcher(None, entry_title, existing).ratio()
                if similarity > similarity_threshold:
                    is_duplicate = True
                    break

            if not is_duplicate:
                normalized = _normalize_scraped_entry(entry, company)
                company_tenders.append(normalized)
                added_count += 1

        merged[company] = company_tenders
        if added_count > 0:
            print(f"      + {company}: 新增 {added_count} 条爬取标讯")
            logger.info(f"{company}: 新增 {added_count} 条爬取标讯")

    return merged


def _sort_by_publish_date(tenders: Dict[str, List[Tender]]) -> Dict[str, List[Tender]]:
    """按发布日期倒序排列标讯（最新发布在前）。

    Args:
        tenders: 标讯字典

    Returns:
        排序后的标讯字典
    """
    sorted_tenders: Dict[str, List[Tender]] = {}

    for company in ["BAPEX", "BGFCL", "SGFL"]:
        if company in tenders:
            company_tenders = tenders[company]
            # 按发布日期排序，最新在前
            company_tenders.sort(
                key=lambda t: t.get_publish_date() or __import__("datetime").datetime.min,
                reverse=True,
            )
            sorted_tenders[company] = company_tenders

    return sorted_tenders


def get_tender_data(
    try_scrape: bool = False,
) -> Tuple[Dict[str, List[Tender]], int, DetectionStats]:
    """获取标讯数据，优先使用爬取结果，失败则用回退数据。

    Args:
        try_scrape: 是否尝试爬取

    Returns:
        (标讯字典, 新增数量, 统计信息)
    """
    # 获取 fallback 数据
    fallback_dict = get_fallback_tenders()
    fallback_tenders: Dict[str, List[Tender]] = {}

    # 将字典转换为 Tender 对象
    for company, tender_list in fallback_dict.items():
        fallback_tenders[company] = [Tender.from_dict(t) for t in tender_list]

    merged_tenders = fallback_tenders

    if try_scrape:
        print("\n  正在爬取最新标讯列表...")
        try:
            listings = scrape_all_listings()
            scraped_count = sum(len(v) for v in listings.values())
            if scraped_count > 0:
                print(f"      ✓ 爬取到 {scraped_count} 条标讯条目")
                logger.info(f"爬取到 {scraped_count} 条标讯条目")
                merged_tenders = _merge_tenders(fallback_tenders, listings)
            else:
                print("      ! 未爬取到新标讯，使用回退数据")
                logger.warning("未爬取到新标讯，使用回退数据")
        except Exception as e:
            print(f"      ! 爬取失败: {e}，使用回退数据")
            logger.error(f"爬取失败: {e}")

    # 检测新标讯并保存历史
    merged_tenders, new_count, stats = detect_new_tenders(merged_tenders)

    if new_count > 0:
        print(f"      ✓ 发现 {new_count} 条新增标讯")
        logger.info(f"发现 {new_count} 条新增标讯")

    # 按发布日期倒序排列
    merged_tenders = _sort_by_publish_date(merged_tenders)

    return merged_tenders, new_count, stats
