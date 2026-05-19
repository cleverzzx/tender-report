# -*- coding: utf-8 -*-
"""数据管理模块 —— 标讯数据获取、合并、PDF解析与过滤"""

import difflib
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from src.fallback import get_fallback_tenders
from src.models import DetectionStats, ScrapedEntry, Tender, TenderField
from src.scraper import scrape_all_listings, parse_pdf_fields
from src.storage import detect_new_tenders

logger = logging.getLogger(__name__)

# 国际标讯类型关键词（排除本地标讯）
_INTERNATIONAL_KEYWORDS = ["আন্তর্জাতিক", "NOA", "বৈদেশিক"]

# NOA 保留天数
_NOA_MAX_AGE_DAYS = 30


def _is_international(tender_type: str, title: str = "") -> bool:
    """判断是否为国际标讯（排除本地标讯）。

    Args:
        tender_type: 标讯类型文本（孟加拉语）
        title: 标讯标题（类型为空时用于辅助判断）

    Returns:
        是否为国际标讯
    """
    if tender_type:
        return any(kw in tender_type for kw in _INTERNATIONAL_KEYWORDS)

    # 类型为空时（如 SGFL），根据标题判断
    if not title:
        return True

    title_upper = title.upper()
    # 国际标讯关键词
    intl_keywords = ["INTERNATIONAL", "FOREIGN", "NOA", "EOI", "EXPRESSION OF INTEREST"]
    if any(kw in title_upper for kw in intl_keywords):
        return True

    # 本地标讯关键词
    local_keywords = ["E-TENDER", "RFQ", "স্থানীয়"]
    if any(kw in title_upper for kw in local_keywords):
        return False

    # 无法判断时保留
    return True


def _is_noa(entry: ScrapedEntry) -> bool:
    """判断是否为 NOA 标讯。"""
    return "NOA" in (entry.tender_type or "").upper()


def _is_tender_expired(tender: Tender, now: Optional[datetime] = None) -> bool:
    """判断标讯是否已过期。

    从字段中提取截止日期，与当前时间比较。

    Args:
        tender: 标讯对象
        now: 当前时间（用于测试）

    Returns:
        True 表示已过期
    """
    if now is None:
        now = datetime.now()

    deadline_fields = ["截止日期", "投标截止日期", "Deadline", "Closing Date", "deadline"]

    for field in tender.fields:
        # 检查 _deadline_dt 属性（从 PDF 解析设置的）
        if hasattr(field, "_deadline_dt") and field._deadline_dt:
            return field._deadline_dt < now

        if field.name in deadline_fields:
            # 尝试解析日期
            try:
                from dateutil import parser as date_parser

                parsed = date_parser.parse(field.value, fuzzy=True)
                if isinstance(parsed, datetime):
                    return parsed < now
            except (ValueError, TypeError):
                pass

    # 没有截止日期信息 → 不视为过期
    return False


def _parse_scraped_date(date_text: str) -> Optional[datetime]:
    """解析爬取的日期文本。"""
    if not date_text:
        return None
    try:
        from dateutil import parser as date_parser

        return date_parser.parse(date_text, fuzzy=True, dayfirst=True)
    except (ValueError, TypeError):
        pass
    return None


def _normalize_scraped_entry(
    entry: ScrapedEntry,
    company: Optional[str] = None,
    pdf_data: Optional[Dict[str, Any]] = None,
) -> Tender:
    """将爬取的原始条目转换为标准标讯格式。

    Args:
        entry: 爬取到的原始条目
        company: 公司名称（可选）
        pdf_data: PDF 解析结果（可选）

    Returns:
        标准化 Tender 对象
    """
    if not company:
        title_lower = entry.title.lower()
        if "bapex" in title_lower:
            company = "BAPEX"
        elif "bgfcl" in title_lower:
            company = "BGFCL"
        elif "sgfl" in title_lower:
            company = "SGFL"

    type_label = ""
    if entry.tender_type:
        type_label = f" | 类型: {entry.tender_type}"

    # 招标编号优先级：PDF > 列表Col2 > 默认
    tender_no = "未知（请查看详情页）"
    if pdf_data and pdf_data.get("tender_no_from_pdf"):
        tender_no = pdf_data["tender_no_from_pdf"]
    elif entry.tender_no:
        tender_no = entry.tender_no

    fields = [
        TenderField("招标编号", tender_no),
        TenderField("发布日期", entry.date_text or "详见详情页"),
    ]

    # 如果 PDF 解析到了关键字段
    if pdf_data and not pdf_data.get("is_scanned") and not pdf_data.get("error"):
        if pdf_data.get("USD"):
            fields.append(TenderField("合同金额(USD)", f"USD {pdf_data['USD']}"))
        if pdf_data.get("BDT"):
            fields.append(TenderField("合同金额(BDT)", f"BDT {pdf_data['BDT']}"))
        if pdf_data.get("deadline"):
            fields.append(TenderField("截止日期", pdf_data["deadline"]))

    fields.append(TenderField("采购内容", entry.title))
    fields.append(
        TenderField(
            "官方来源",
            f"<a href='{entry.url}' color='blue'>点击查看详情页</a>" if entry.url else "未提供",
        )
    )

    if entry.pdf_url:
        status = ""
        if pdf_data:
            if pdf_data.get("is_scanned"):
                status = " (扫描件，无法自动提取)"
            elif pdf_data.get("error"):
                status = f" (解析失败)"
        fields.append(
            TenderField(
                "PDF下载",
                f"<a href='{entry.pdf_url}' color='blue'>点击下载招标文件(PDF){status}</a>",
            )
        )

    return Tender(
        title=entry.title,
        key=f"状态: <b>新爬取</b> | 来源: {company or 'Unknown'}{type_label}",
        special="<b>从官网爬取</b> | 请访问详情页获取完整信息",
        fields=fields,
        _source="scraped",
        _url=entry.url,
    )


def _enrich_with_pdf(
    tenders: Dict[str, List[Tender]],
    max_workers: int = 3,
) -> None:
    """并发下载解析 PDF，补全标讯信息。

    Args:
        tenders: 标讯字典（原地修改）
        max_workers: 并发数
    """
    # 收集所有需要解析 PDF 的标讯
    tasks: List[Tuple[str, int, str]] = []  # (company, index, pdf_url)
    for company, tlist in tenders.items():
        for i, t in enumerate(tlist):
            if t._source != "scraped":
                continue
            # 从 fields 中找 PDF 链接
            pdf_url = ""
            for f in t.fields:
                if f.name == "PDF下载":
                    # 从 HTML 中提取 URL
                    import re

                    m = re.search(r"href='([^']+)'", f.value)
                    if m:
                        pdf_url = m.group(1)
                    break
            if pdf_url:
                tasks.append((company, i, pdf_url))

    if not tasks:
        return

    print(f"      ⏳ 正在解析 {len(tasks)} 个 PDF 文件...")
    logger.info(f"开始解析 {len(tasks)} 个 PDF 文件")

    def parse_one(task: Tuple[str, int, str]) -> Tuple[str, int, Dict[str, Any]]:
        company, idx, pdf_url = task
        return company, idx, parse_pdf_fields(pdf_url)

    completed = 0
    scanned = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(parse_one, t): t for t in tasks}
        for future in as_completed(futures):
            company, idx, pdf_data = future.result()
            completed += 1
            if pdf_data.get("is_scanned"):
                scanned += 1

            # 更新标讯字段
            tender = tenders[company][idx]
            if not pdf_data.get("is_scanned") and not pdf_data.get("error"):
                if pdf_data.get("USD"):
                    tender.fields.insert(
                        2, TenderField("合同金额(USD)", f"USD {pdf_data['USD']}")
                    )
                if pdf_data.get("BDT"):
                    tender.fields.insert(
                        3, TenderField("合同金额(BDT)", f"BDT {pdf_data['BDT']}")
                    )
                if pdf_data.get("deadline"):
                    tender.fields.insert(
                        4, TenderField("截止日期", pdf_data["deadline"])
                    )

    if scanned > 0:
        print(f"      ⚠ {scanned}/{completed} 个 PDF 为扫描件，无法自动提取")
        logger.info(f"{scanned}/{completed} 个 PDF 为扫描件")


def _filter_tenders(
    tenders: Dict[str, List[Tender]],
    now: Optional[datetime] = None,
) -> Dict[str, List[Tender]]:
    """过滤标讯：移除过期标讯和超过一个月的老 NOA。

    Args:
        tenders: 标讯字典
        now: 当前时间

    Returns:
        过滤后的标讯字典
    """
    if now is None:
        now = datetime.now()

    noa_cutoff = now - timedelta(days=_NOA_MAX_AGE_DAYS)
    filtered: Dict[str, List[Tender]] = {}

    for company, tlist in tenders.items():
        kept: List[Tender] = []
        expired_count = 0
        old_noa_count = 0
        for t in tlist:
            # NOA 月限过滤
            is_noa = t.is_noa()
            if is_noa:
                pub_date = t.get_publish_date()
                if pub_date and pub_date < noa_cutoff:
                    old_noa_count += 1
                    logger.debug(f"  过滤旧NOA: {t.title[:60]} (发布于 {pub_date.date()})")
                    continue

            # 过期过滤
            if _is_tender_expired(t, now):
                expired_count += 1
                logger.debug(f"  过滤过期标讯: {t.title[:60]}")
                continue

            kept.append(t)

        if expired_count > 0:
            print(f"      - {company}: 过滤 {expired_count} 条过期标讯")
            logger.info(f"{company}: 过滤 {expired_count} 条过期标讯")
        if old_noa_count > 0:
            print(f"      - {company}: 过滤 {old_noa_count} 条旧NOA (>{_NOA_MAX_AGE_DAYS}天)")
            logger.info(f"{company}: 过滤 {old_noa_count} 条旧NOA")

        filtered[company] = kept

    return filtered


def _merge_tenders(
    fallback_tenders: Dict[str, List[Tender]],
    scraped_listings: Dict[str, List[ScrapedEntry]],
    similarity_threshold: float = 0.70,
) -> Dict[str, List[Tender]]:
    """合并 fallback 数据和爬取数据，去重并标记来源。"""
    SOURCE_TO_COMPANY: Dict[str, Optional[str]] = {
        "BAPEX": "BAPEX",
        "BAPEX_NOA": "BAPEX",
        "BGFCL_portal": "BGFCL",
        "SGFL": "SGFL",
        "Petrobangla": None,
    }

    merged: Dict[str, List[Tender]] = {}
    for company in ["BAPEX", "BGFCL", "SGFL"]:
        company_tenders = fallback_tenders.get(company, []).copy()
        existing_urls = {t._url for t in company_tenders if t._url}
        existing_titles = [t.title.lower() for t in company_tenders]

        company_scraped: List[ScrapedEntry] = []
        for source_name, entries in scraped_listings.items():
            target = SOURCE_TO_COMPANY.get(source_name)
            if target == company:
                company_scraped.extend(entries)
            elif target is None:
                for entry in entries:
                    inferred = _infer_company_from_entry(entry)
                    if inferred == company:
                        company_scraped.append(entry)

        # 过滤本地标讯
        international: List[ScrapedEntry] = []
        filtered_count = 0
        for entry in company_scraped:
            if _is_international(entry.tender_type, entry.title):
                international.append(entry)
            else:
                filtered_count += 1
        if filtered_count > 0:
            logger.info(f"{company}: 过滤掉 {filtered_count} 条本地标讯")
            print(f"      - {company}: 过滤 {filtered_count} 条本地标讯")
        company_scraped = international

        if not company_scraped:
            merged[company] = company_tenders
            continue

        added_count = 0
        for entry in company_scraped:
            entry_title = entry.title.lower()
            if not entry_title or len(entry_title) < 10:
                continue
            if entry.url and entry.url in existing_urls:
                continue
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
    """从标讯标题推断所属公司。"""
    title_lower = title.lower()
    url_lower = url.lower()
    if "sgfl.gov.bd" in url_lower or "office-sgfl" in url_lower:
        return "SGFL"
    if "bapex.com.bd" in url_lower or "office-bapex" in url_lower:
        return "BAPEX"
    if "bgfcl" in url_lower:
        return "BGFCL"
    if "sgfl" in title_lower or "sylhet" in title_lower:
        return "SGFL"
    if "bapex" in title_lower:
        return "BAPEX"
    if "bgfcl" in title_lower:
        return "BGFCL"
    return None


def _infer_company_from_entry(entry: ScrapedEntry) -> Optional[str]:
    """从爬取条目推断所属公司。"""
    return _infer_company_from_title(entry.title, entry.url or "")


def _sort_by_publish_date(tenders: Dict[str, List[Tender]]) -> Dict[str, List[Tender]]:
    """按发布日期倒序排列。"""
    sorted_tenders: Dict[str, List[Tender]] = {}
    for company in ["BAPEX", "BGFCL", "SGFL"]:
        if company in tenders:
            company_tenders = tenders[company]
            company_tenders.sort(
                key=lambda t: t.get_publish_date() or __import__("datetime").datetime.min,
                reverse=True,
            )
            sorted_tenders[company] = company_tenders
    return sorted_tenders


def get_tender_data(
    try_scrape: bool = False,
) -> Tuple[Dict[str, List[Tender]], int, DetectionStats]:
    """获取标讯数据，爬取 → 合并 → PDF解析 → 过滤 → 排序。

    Args:
        try_scrape: 是否尝试爬取

    Returns:
        (标讯字典, 新增数量, 统计信息)
    """
    fallback_dict = get_fallback_tenders()
    fallback_tenders: Dict[str, List[Tender]] = {}
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

                # PDF 解析补全信息
                _enrich_with_pdf(merged_tenders)
            else:
                print("      ! 未爬取到新标讯，使用回退数据")
                logger.warning("未爬取到新标讯，使用回退数据")
        except Exception as t:
            print(f"      ! 爬取失败: {t}，使用回退数据")
            logger.error(f"爬取失败: {t}")

    # 统一过滤：过期 + 旧 NOA（不论是否爬取）
    merged_tenders = _filter_tenders(merged_tenders)

    # 检测新标讯并保存历史
    merged_tenders, new_count, stats = detect_new_tenders(merged_tenders)

    if new_count > 0:
        print(f"      ✓ 发现 {new_count} 条新增标讯")
        logger.info(f"发现 {new_count} 条新增标讯")

    merged_tenders = _sort_by_publish_date(merged_tenders)

    return merged_tenders, new_count, stats
