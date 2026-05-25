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

# NOA 保留天数（中标通知书，招标已结束，保留 5 天）
_NOA_MAX_AGE_DAYS = 14


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

    # 类型为空时（如 Petrobangla 来源），根据标题判断
    if not title:
        return True

    title_upper = title.upper()
    # 国际标讯关键词（英文 + 孟加拉语）
    intl_keywords = [
        "INTERNATIONAL", "FOREIGN", "NOA", "EOI", "EXPRESSION OF INTEREST",
        "আন্তর্জাতিক",  # 国际
        "আন্তজার্তিক",  # 国际（变体）
        "বৈদেশিক",      # 外国/海外
    ]
    if any(kw in title_upper for kw in intl_keywords):
        return True

    # 本地标讯关键词（英文 + 孟加拉语）
    local_keywords = [
        "E-TENDER", "RFQ", "RFX", "RFP",
        "স্থানীয়",      # 本地
    ]
    if any(kw in title_upper for kw in local_keywords):
        return False

    # 类型为空且标题无任何国际标记 → 默认为本地标讯（防止本地采购混入）
    return False


def _is_noa(entry: ScrapedEntry) -> bool:
    """判断是否为 NOA 标讯。"""
    return "NOA" in (entry.tender_type or "").upper()


def _is_tender_expired(tender: Tender, now: Optional[datetime] = None) -> bool:
    """判断标讯是否已过期。

    从字段中提取截止日期，与当前时间比较。
    对标注了延期（Extension）的标讯给予 7 天缓冲期。

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
        if field.name in deadline_fields:
            # 尝试解析日期
            try:
                from dateutil import parser as date_parser

                # 清理日期字符串（移除时区缩写如 BST）
                date_str = field.value.strip()
                # 移除常见时区缩写，保留日期时间部分
                import re

                # 先尝试提取 ISO 格式日期 (2026-05-18T11:30:00)
                iso_match = re.search(r'(\d{4}-\d{2}-\d{2})[T\s](\d{2}:\d{2}(?::\d{2})?)', date_str)
                if iso_match:
                    date_part = iso_match.group(1)
                    time_part = iso_match.group(2)
                    parsed = datetime.strptime(f"{date_part} {time_part}", "%Y-%m-%d %H:%M")
                    return parsed < now

                # 提取日期部分（忽略时区如 BST）
                date_match = re.search(
                    r'(\d{4}-\d{2}-\d{2})\s+(\d{1,2}:\d{2}(?::\d{2})?)',
                    date_str
                )
                if date_match:
                    date_part = date_match.group(1)
                    time_part = date_match.group(2)
                    if len(time_part.split(':')) == 2:
                        parsed = datetime.strptime(f"{date_part} {time_part}", "%Y-%m-%d %H:%M")
                    else:
                        parsed = datetime.strptime(f"{date_part} {time_part}", "%Y-%m-%d %H:%M:%S")
                    return parsed < now

                # 回退到 dateutil 解析
                parsed = date_parser.parse(date_str, fuzzy=True)
                if isinstance(parsed, datetime):
                    # 忽略时区信息，只比较本地时间
                    parsed_naive = parsed.replace(tzinfo=None)
                    return parsed_naive < now
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


def _format_date_for_display(date_str: str) -> str:
    """统一日期显示格式：YYYY-MM-DD 或 YYYY-MM-DD HH:MM。

    处理各种来源的日期格式：
      - ISO: 2026-06-15T00:00:00 → 2026-06-15
      - ISO 有时间: 2026-06-18T12:00:00 → 2026-06-18 12:00
      - 带时区: 2026-06-18 12:00 BST → 2026-06-18 12:00
      - 带"约"字: 约2026-06-12 → 2026-06-12
      - DD-MM-YYYY: 14-05-2026 → 2025-05-14
      - 多日期: 2026-01-28 / 延期公告 2026-04-13 → 2026-01-28 / 2026-04-13

    Args:
        date_str: 原始日期字符串

    Returns:
        统一格式后的日期字符串
    """
    if not date_str:
        return date_str

    import re

    # 处理"约"字前缀
    date_str = re.sub(r'^约\s*', '', date_str.strip())

    # 多日期情况（用 / 或 延期公告 分隔）
    # 提取所有日期部分，统一格式后重新组合
    date_patterns = [
        r'(\d{4}-\d{2}-\d{2})',  # YYYY-MM-DD
        r'(\d{4}/\d{2}/\d{2})',  # YYYY/MM/DD
    ]

    all_dates = []
    for pattern in date_patterns:
        matches = re.findall(pattern, date_str)
        all_dates.extend(matches)

    if len(all_dates) > 1:
        # 多日期情况，只保留日期部分，移除时间
        return " / ".join(sorted(set(all_dates)))

    # 单日期处理
    if all_dates:
        base_date = all_dates[0]
    else:
        # 尝试从文本中解析日期
        base_date = date_str

    # 检查是否是 DD-MM-YYYY 格式（如 14-05-2026）
    dd_mm_yyyy_match = re.search(r'^(\d{1,2})-(\d{1,2})-(\d{4})$', base_date.strip())
    if dd_mm_yyyy_match:
        day = dd_mm_yyyy_match.group(1).zfill(2)
        month = dd_mm_yyyy_match.group(2).zfill(2)
        year = dd_mm_yyyy_match.group(3)
        return f"{year}-{month}-{day}"

    # ISO 格式（含 T 分隔符）
    if "T" in base_date:
        parts = base_date.split("T")
        date_part = parts[0]
        time_part = parts[1] if len(parts) > 1 else ""
        # 提取 HH:MM 部分，忽略秒和时区
        time_match = re.search(r'(\d{2}:\d{2})', time_part)
        if time_match and time_part != "00:00:00":
            return f"{date_part} {time_match.group(1)}"
        return date_part

    # 处理普通日期+时间+时区格式
    # 如：2026-06-18 12:00 BST → 2026-06-18 12:00
    time_match = re.search(r'^(\d{4}-\d{2}-\d{2})\s+(\d{1,2}:\d{2})', base_date)
    if time_match:
        date_part = time_match.group(1)
        time_part = time_match.group(2)
        # 标准化时间为 HH:MM 格式
        hour, minute = time_part.split(':')
        return f"{date_part} {hour.zfill(2)}:{minute}"

    # 纯日期格式
    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', base_date)
    if date_match:
        return date_match.group(1)

    return date_str


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

    # 招标编号优先级：PDF > 列表 tender_no > 标题解析 > 默认
    tender_no = "未知（请查看详情页）"
    if pdf_data and pdf_data.get("tender_no_from_pdf"):
        tender_no = pdf_data["tender_no_from_pdf"]
    elif entry.tender_no:
        tender_no = entry.tender_no
    else:
        # 从标题解析招标编号（常见格式）
        import re
        # 匹配 Ref. No. XXX/XXX/XXX 或 Tender No: XXX 等格式
        patterns = [
            r'Ref\.?\s*No\.?\s*:?\s*([A-Z0-9/\-().]+)',
            r'Tender\s+No\.?\s*:?\s*([A-Z0-9/\-().]+)',
            r'(?: Tender |^)([A-Z]{2,10}/[A-Z0-9/\-]+(?:/\d{4})?)',
        ]
        for pattern in patterns:
            m = re.search(pattern, entry.title, re.IGNORECASE)
            if m:
                tender_no = m.group(1).strip()
                # 清理结尾的标点
                tender_no = re.sub(r'[\s,;:]+$', '', tender_no)
                break

    fields = [
        TenderField("招标编号", tender_no),
        TenderField("发布日期", _format_date_for_display(entry.date_text) or "详见详情页"),
    ]

    # 如果 PDF 解析到了关键字段
    if pdf_data and not pdf_data.get("is_scanned") and not pdf_data.get("error"):
        if pdf_data.get("USD"):
            fields.append(TenderField("合同金额(USD)", f"USD {pdf_data['USD']}"))
        if pdf_data.get("BDT"):
            fields.append(TenderField("合同金额(BDT)", f"BDT {pdf_data['BDT']}"))
        if pdf_data.get("deadline"):
            fields.append(TenderField("截止日期", _format_date_for_display(pdf_data["deadline"])))

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
                        4, TenderField("截止日期", _format_date_for_display(pdf_data["deadline"]))
                    )

    if scanned > 0:
        print(f"      ⚠ {scanned}/{completed} 个 PDF 为扫描件，无法自动提取")
        logger.info(f"{scanned}/{completed} 个 PDF 为扫描件")


def _enrich_with_detail_page(
    tenders: Dict[str, List[Tender]], max_workers: int = 3
) -> None:
    """对爬取标讯访问详情页补充完整信息。

    提取标讯类型、详细描述、发布日期、存档日期等字段，
    并更新 key / special 让展示更清晰。

    Args:
        tenders: 标讯字典（原地修改）
        max_workers: 并发数
    """
    from src.scraper import scrape_detail_page

    tasks: List[Tuple[str, int, str]] = []
    for company, tlist in tenders.items():
        for i, t in enumerate(tlist):
            if t._source != "scraped":
                continue
            if t._url:
                tasks.append((company, i, t._url))

    if not tasks:
        return

    print(f"      ⏳ 正在抓取 {len(tasks)} 个详情页补充信息...")
    logger.info(f"开始抓取 {len(tasks)} 个详情页")

    def fetch_one(task: Tuple[str, int, str]) -> Tuple[str, int, Optional[Dict[str, Any]]]:
        company, idx, url = task
        return company, idx, scrape_detail_page(url)

    enriched = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_one, t): t for t in tasks}
        for future in as_completed(futures):
            company, idx, detail_data = future.result()
            if not detail_data:
                continue

            tender = tenders[company][idx]
            raw_fields = detail_data.get("fields", {})

            # ---- 1. 补充截止日期 ----
            has_deadline = any(
                f.name in ("截止日期", "投标截止日期", "Deadline", "Closing Date")
                for f in tender.fields
            )
            if not has_deadline:
                deadline_added = False
                for key in ("parsed_截止日期", "parsed_投标截止日期"):
                    if key in detail_data:
                        tender.fields.insert(
                            2, TenderField("截止日期", _format_date_for_display(detail_data[key]))
                        )
                        enriched += 1
                        deadline_added = True
                        break

                # 详情页也没有真实截止日期 → 标注"详见招标文件PDF"
                if not deadline_added:
                    import re
                    pdf_url = ""
                    for f in tender.fields:
                        if f.name == "PDF下载":
                            m = re.search(r"href='([^']+)'", f.value)
                            if m:
                                pdf_url = m.group(1)
                            break
                    if pdf_url:
                        tender.fields.insert(
                            2,
                            TenderField(
                                "截止日期",
                                f"<a href='{pdf_url}' color='blue'>详见招标文件PDF</a>",
                            ),
                        )
                    else:
                        tender.fields.insert(
                            2, TenderField("截止日期", "详见官网招标文件")
                        )

            # ---- 2. 更新发布日期（详情页解析结果更准确）----
            if "parsed_发布日期" in detail_data:
                formatted_pub = _format_date_for_display(detail_data["parsed_发布日期"])
                # 查找并更新已有的发布日期字段
                pub_found = False
                for fi, f in enumerate(tender.fields):
                    if f.name == "发布日期":
                        tender.fields[fi] = TenderField("发布日期", formatted_pub)
                        pub_found = True
                        break
                if not pub_found:
                    tender.fields.insert(1, TenderField("发布日期", formatted_pub))

            # ---- 3. 提取标讯类型并翻译 ----
            tender_type = raw_fields.get("দরপত্রের ধরণ", "")
            # 孟加拉语类型翻译
            type_translation = {
                "আন্তর্জাতিক NOA": "国际 NOA",
                "আন্তর্জাতিক দরপত্র": "国际招标",
                "বৈদেশিক-দরপত্র": "国际招标",
                "বৈদেশিক দরপত্র": "国际招标",
                "আন্তর্জাতিক": "国际招标",
                "International Tender": "国际招标",
                "Foreign/International Tender": "国际招标",
                "স্থানীয় দরপত্র": "本地招标",
                "স্থানীয় দরপত্র (ই-জিপি সহ)": "本地招标(e-GP)",
            }
            if tender_type in type_translation:
                tender_type = type_translation[tender_type]
            elif not tender_type:
                # 尝试从 title 推断
                if "NOA" in tender.title.upper():
                    tender_type = "国际 NOA"
                elif "re-tender" in tender.title.lower():
                    tender_type = "国际重新招标"
                elif "international" in tender.title.lower():
                    tender_type = "国际招标"
                elif "EOI" in tender.title.upper():
                    tender_type = "意向书征集"

            # 更新 key 字段，包含类型和来源
            type_info = f"类型: <b>{tender_type}</b>" if tender_type else ""
            pub_info = ""
            for f in tender.fields:
                if f.name == "发布日期":
                    pub_info = f"发布: {f.value}"
                    break
            key_parts = [p for p in [type_info, pub_info, f"来源: {company}"] if p]
            tender.key = " | ".join(key_parts)

            # 更新 special 字段
            special_parts = ["<b>从官网实时爬取</b>"]

            # 存档日期（过滤掉明显占位日期如 2030-12-31）
            archive_raw = raw_fields.get("আর্কাইভ তারিখ", "")
            if archive_raw:
                from src.scraper import _parse_date
                archive_dt = _parse_date(archive_raw)
                if archive_dt and archive_dt.year < 2030:
                    special_parts.append(f"存档日期: {archive_dt.strftime('%Y-%m-%d')}")

            # 引导用户查看 PDF 获取完整信息
            pdf_url = ""
            import re
            for f in tender.fields:
                if f.name == "PDF下载":
                    m = re.search(r"href='([^']+)'", f.value)
                    if m:
                        pdf_url = m.group(1)
                    break
            if pdf_url:
                special_parts.append(
                    f"<a href='{pdf_url}' color='blue'>完整招标要求和截止日期详见PDF</a>"
                )
            else:
                special_parts.append("请访问详情页获取完整招标文件")
            tender.special = " | ".join(special_parts)

            # ---- 4. 补充详细描述和采购内容 ----
            detail = ""

            # 优先使用详情页解析的描述字段（如 শিরোনাম 标题）
            if "parsed_描述" in detail_data:
                detail = detail_data["parsed_描述"].strip()

            # 也检查原始字段
            if not detail or len(detail) < 10:
                detail = raw_fields.get("বিস্তারিত", "")
                desc_fields = [
                    "বিস্তারিত", "দরপত্রের বিবরণ", "স্পেসিফিকেশন",
                    "বিষয়", "Subject", "Description", "Details",
                    "Tender Description", "Scope of Work", "Work Description",
                ]
                for desc_field in desc_fields:
                    if desc_field in raw_fields:
                        candidate = raw_fields[desc_field].strip()
                        if len(candidate) > len(detail):
                            detail = candidate

            # 清理 detail 文本
            if detail:
                detail = detail.replace("\n", " ").replace("\r", " ")
                detail = " ".join(detail.split())  # 去除多余空格

            if detail and len(detail) > 10:
                # 去重：如果详细描述和标题差异较大才添加项目详情字段
                if detail.lower() not in tender.title.lower() and len(detail) > len(tender.title):
                    tender.fields.insert(
                        3, TenderField("项目详情", detail[:500])
                    )

                # 更新采购内容：优先使用详情页描述
                for fi, f in enumerate(tender.fields):
                    if f.name == "采购内容":
                        current = f.value.strip()
                        # 如果详情页描述明显比当前采购内容更有信息量，则替换
                        should_update = False
                        # 当前是标题，且标题主要是编号+日期（没有实质性描述）
                        if current == tender.title and len(detail) > len(current) * 0.5:
                            should_update = True
                        # 当前太短
                        elif len(current) < 80 and len(detail) > len(current):
                            should_update = True
                        # 详情页描述明显更长
                        elif len(detail) > len(current) + 20:
                            should_update = True

                        if should_update:
                            cleaner = detail[:300]
                            tender.fields[fi] = TenderField("采购内容", cleaner)
                        break
            else:
                # 详情页没有描述 → 引导用户查看PDF
                for fi, f in enumerate(tender.fields):
                    if f.name == "采购内容":
                        current = f.value.strip()
                        if len(current) < 60:
                            tender.fields[fi] = TenderField(
                                "采购内容",
                                f"{current}（完整技术规格和投标要求详见PDF招标文件）"
                            )
                        break

            # ---- 5. 补充其他可用字段 ----
            # 内容类型（翻译孟加拉语）
            content_type = raw_fields.get("কন্টেন্ট টাইপ", "")
            if content_type:
                # 翻译常见类型
                type_map = {
                    "টেন্ডার (দরপত্র)": "招标公告",
                    "নোটিশ": "通知",
                    "সংবাদ": "新闻",
                }
                content_type_cn = type_map.get(content_type, content_type)
                if not any(f.name == "内容类型" for f in tender.fields):
                    tender.fields.insert(0, TenderField("内容类型", content_type_cn))

    if enriched > 0:
        print(f"      ✓ {enriched}/{len(tasks)} 个详情页补充了截止日期")
        logger.info(f"{enriched}/{len(tasks)} 个详情页补充了截止日期")
    else:
        print(f"      ✓ {len(tasks)} 个详情页信息已补充")
        logger.info(f"{len(tasks)} 个详情页信息已补充")


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
        updated_count = 0
        for entry in company_scraped:
            entry_title = entry.title.lower()
            if not entry_title or len(entry_title) < 10:
                continue
            if entry.url and entry.url in existing_urls:
                continue
            is_duplicate = False
            match_idx = -1
            for idx, existing in enumerate(existing_titles):
                similarity = difflib.SequenceMatcher(None, entry_title, existing).ratio()
                if similarity > similarity_threshold:
                    is_duplicate = True
                    match_idx = idx
                    break
            if not is_duplicate:
                normalized = _normalize_scraped_entry(entry, company)
                company_tenders.append(normalized)
                existing_titles.append(entry_title)
                if entry.url:
                    existing_urls.add(entry.url)
                added_count += 1
            elif match_idx >= 0 and entry.date_text:
                # 去重但更新：用爬取数据补全 fallback 标讯的截止日期和链接
                match_tender = company_tenders[match_idx]
                has_deadline = any(
                    f.name in ("截止日期", "投标截止日期", "Deadline", "Closing Date")
                    for f in match_tender.fields
                )
                if not has_deadline and entry.date_text:
                    match_tender.fields.insert(
                        0, TenderField("截止日期", _format_date_for_display(entry.date_text))
                    )
                # 如果爬取条目有 PDF 链接且 fallback 没有，补上
                if entry.pdf_url:
                    has_pdf = any(f.name == "PDF下载" for f in match_tender.fields)
                    if not has_pdf:
                        match_tender.fields.append(
                            TenderField("PDF下载", entry.pdf_url)
                        )
                # 更新详情页链接
                if entry.url and not match_tender._url:
                    match_tender._url = entry.url
                # 保留更详细的采购内容
                scraped_procurement = entry.title
                fallback_procurement = ""
                for f in match_tender.fields:
                    if f.name == "采购内容":
                        fallback_procurement = f.value
                        break

                # 判断哪个采购内容更有实质描述性
                def _extract_core_content(text: str) -> str:
                    """提取核心描述内容（去除常见前缀）。"""
                    import re
                    t = text.lower()
                    # 去除常见前缀
                    prefixes = [
                        r'international tender for procurement of\s*',
                        r'international tender notice:?\s*',
                        r'procurement of\s*',
                        r'request for expressions of interest \(eoi\) for\s*',
                        r'eoi for\s*',
                    ]
                    for p in prefixes:
                        t = re.sub(p, '', t)
                    return t.strip()

                scraped_core = _extract_core_content(scraped_procurement)
                fallback_core = _extract_core_content(fallback_procurement)

                # 判断爬取标题是否主要是编号+日期（缺乏实质性描述）
                def _is_ref_date_title(title: str) -> bool:
                    """判断标题是否主要是招标编号+日期格式。"""
                    import re
                    title_upper = title.upper()
                    has_ref_no = bool(re.search(r'REF\.?\s*NO\.?', title_upper))
                    has_tender_no = bool(re.search(r'TENDER\s+NO', title_upper))
                    has_date = bool(re.search(r'DATE|DATED|\d{4}-\d{2}-\d{2}', title_upper))
                    return (has_ref_no or has_tender_no) and has_date

                should_update = False
                # 情况1: 爬取标题是编号+日期格式，fallback 有实质描述 → 保留 fallback
                if _is_ref_date_title(scraped_procurement) and not _is_ref_date_title(fallback_procurement):
                    should_update = False
                # 情况2: 爬取标题去掉前缀后，和 fallback 核心内容相似 → 保留 fallback（更简洁）
                elif scraped_core in fallback_core or fallback_core in scraped_core:
                    should_update = False
                # 情况3: 爬取标题去掉前缀后，明显比 fallback 更长更有信息 → 更新
                elif len(scraped_core) > len(fallback_core) + 10:
                    should_update = True

                if should_update:
                    for fi, f in enumerate(match_tender.fields):
                        if f.name == "采购内容":
                            match_tender.fields[fi] = TenderField("采购内容", scraped_procurement)
                            break
                updated_count += 1

        merged[company] = company_tenders
        if added_count > 0:
            print(f"      + {company}: 新增 {added_count} 条爬取标讯")
            logger.info(f"{company}: 新增 {added_count} 条爬取标讯")
        if updated_count > 0:
            print(f"      ~ {company}: 更新 {updated_count} 条已有标讯（截止日期/链接）")
            logger.info(f"{company}: 更新 {updated_count} 条已有标讯")

    return merged


def _infer_company_from_title(title: str, url: str = "") -> Optional[str]:
    """从标讯标题推断所属公司（支持英文和孟加拉语）。"""
    title_lower = title.lower()
    url_lower = url.lower()

    # 1. URL 推断（优先级最高）
    if "sgfl.gov.bd" in url_lower or "office-sgfl" in url_lower:
        return "SGFL"
    if "bapex.com.bd" in url_lower or "office-bapex" in url_lower:
        return "BAPEX"
    if "bgfcl" in url_lower or "office-bgfcl" in url_lower:
        return "BGFCL"

    # 2. 孟加拉语公司名称匹配（Petrobangla 来源的标讯多为孟加拉语标题）
    #    এসজিএফএল = SGFL, বাপেক্স = BAPEX, বিজিএফসিএল = BGFCL
    if "এসজিএফএল" in title or "এস.জি.এফ.এল" in title:
        return "SGFL"
    if "বাপেক্স" in title or "বি.এ.পি.ই.এক্স" in title:
        return "BAPEX"
    if "বিজিএফসিএল" in title or "বি.জি.এফ.সি.এল" in title:
        return "BGFCL"

    # 3. 英文名称匹配
    if "sgfl" in title_lower or "sylhet" in title_lower:
        return "SGFL"
    if "bapex" in title_lower:
        return "BAPEX"
    if "bgfcl" in title_lower:
        return "BGFCL"

    # 4. URL 中的孟加拉语公司名（部分 URL 包含孟加拉语 slug）
    if "এসজিএফএল" in url_lower:
        return "SGFL"
    if "বাপেক্স" in url_lower:
        return "BAPEX"
    if "বিজিএফসিএল" in url_lower:
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

                # 详情页补充截止日期（对没有截止日期的爬取标讯）
                _enrich_with_detail_page(merged_tenders)
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
