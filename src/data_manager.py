# -*- coding: utf-8 -*-
"""数据管理模块 —— 标讯数据获取与合并"""

import difflib
import logging
from typing import Dict, List, Optional, Tuple

from src.fallback import get_fallback_tenders
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
    similarity_threshold: float = 0.70,
) -> Dict[str, List[Tender]]:
    """合并 fallback 数据和爬取数据，去重并标记来源。

    去重策略：
    - URL 完全相同 → 直接视为重复
    - 标题相似度 > threshold → 视为同一条
    - 多来源（如 Petrobangla）自动按标题推断公司归属

    Args:
        fallback_tenders: fallback 标讯数据
        scraped_listings: 爬取到的标讯列表（key 为来源名，如 BAPEX / Petrobangla / SGFL / BGFCL_portal）
        similarity_threshold: 相似度阈值（默认 0.70）

    Returns:
        合并后的标讯字典
    """
    # 来源 → 公司映射：Petrobangla 是汇总站，条目需按标题推断公司
    SOURCE_TO_COMPANY: Dict[str, Optional[str]] = {
        "BAPEX": "BAPEX",
        "BGFCL_portal": "BGFCL",
        "SGFL": "SGFL",
        "Petrobangla": None,  # 需要推断
    }

    merged: Dict[str, List[Tender]] = {}
    # 先收集每个公司的 fallback + scraped
    for company in ["BAPEX", "BGFCL", "SGFL"]:
        company_tenders = fallback_tenders.get(company, []).copy()
        existing_urls = {t._url for t in company_tenders if t._url}
        existing_titles = [t.title.lower() for t in company_tenders]

        # 收集属于该公司的爬取条目
        company_scraped: List[ScrapedEntry] = []
        for source_name, entries in scraped_listings.items():
            target = SOURCE_TO_COMPANY.get(source_name)
            if target == company:
                company_scraped.extend(entries)
            elif target is None:  # Petrobangla — 按标题+URL 推断
                for entry in entries:
                    inferred = _infer_company_from_entry(entry)
                    if inferred == company:
                        company_scraped.append(entry)

        if not company_scraped:
            merged[company] = company_tenders
            continue

        added_count = 0
        for entry in company_scraped:
            entry_title = entry.title.lower()
            if not entry_title or len(entry_title) < 10:
                continue

            # URL 去重
            if entry.url and entry.url in existing_urls:
                continue

            # 标题相似度去重
            is_duplicate = False
            for existing in existing_titles:
                similarity = difflib.SequenceMatcher(None, entry_title, existing).ratio()
                if similarity > similarity_threshold:
                    is_duplicate = True
                    break

            if not is_duplicate:
                normalized = _normalize_scraped_entry(entry, company)
                company_tenders.append(normalized)
                existing_titles.append(entry_title)
                if entry.url:
                    existing_urls.add(entry.url)
                added_count += 1

        merged[company] = company_tenders
        if added_count > 0:
            print(f"      + {company}: 新增 {added_count} 条爬取标讯")
            logger.info(f"{company}: 新增 {added_count} 条爬取标讯")

    return merged


def _infer_company_from_title(title: str, url: str = "") -> Optional[str]:
    """从标讯标题推断所属公司。

    Args:
        title: 标讯标题
        url: 标讯 URL（辅助推断）

    Returns:
        公司名或 None
    """
    title_lower = title.lower()
    url_lower = url.lower()

    # URL 辅助推断（优先级最高 — URL 域名是最可靠的）
    if "sgfl.gov.bd" in url_lower or "office-sgfl" in url_lower:
        return "SGFL"
    if "bapex.com.bd" in url_lower or "office-bapex" in url_lower:
        return "BAPEX"
    if "bgfcl" in url_lower:
        return "BGFCL"

    # 标题关键词推断
    if "sgfl" in title_lower or "sylhet" in title_lower:
        return "SGFL"
    if "bapex" in title_lower:
        return "BAPEX"
    if "bgfcl" in title_lower:
        return "BGFCL"

    # 无法推断
    return None


def _infer_company_from_entry(entry: ScrapedEntry) -> Optional[str]:
    """从爬取条目推断所属公司（综合标题 + URL）。"""
    return _infer_company_from_title(entry.title, entry.url or "")


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
