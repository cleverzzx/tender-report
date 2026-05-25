# -*- coding: utf-8 -*-
"""标讯爬虫模块 —— 链接校验 + 列表页爬取 + 详情页数据提取 v3.1"""

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, cast
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from src.urls import LISTING_URLS, OFFICIAL_URLS
from src.models import ScrapedEntry, ValidationResult

logger = logging.getLogger(__name__)

# 请求头
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,bn;q=0.8",
    "Accept-Encoding": "gzip, deflate",
}

REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_DELAY = 2  # 秒

# 已知 SSL 证书有问题的站点（政府网站常见）
KNOWN_SSL_ISSUES = {
    "bgfcl.portal.gov.bd",
    "sgfl.gov.bd",
}


class RetryableError(Exception):
    """可重试的错误"""

    pass


def retry_on_failure(max_retries: int = MAX_RETRIES, delay: float = RETRY_DELAY) -> Callable:
    """重试装饰器。

    Args:
        max_retries: 最大重试次数
        delay: 重试间隔（秒）

    Returns:
        装饰器函数
    """

    def decorator(func: Callable) -> Callable:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except RetryableError as e:
                    last_exception = e
                    if attempt < max_retries:
                        wait_time = delay * (2**attempt)  # 指数退避
                        logger.warning(
                            f"{func.__name__} 失败，{wait_time}s 后重试 "
                            f"({attempt + 1}/{max_retries}): {e}"
                        )
                        time.sleep(wait_time)
                    else:
                        raise
                except Exception:
                    raise
            if last_exception:
                raise last_exception
            return None

        return wrapper

    return decorator


def _should_skip_ssl_verification(url: str) -> bool:
    """判断是否应该跳过 SSL 验证。

    Args:
        url: URL 地址

    Returns:
        是否跳过 SSL 验证
    """
    for domain in KNOWN_SSL_ISSUES:
        if domain in url:
            return True
    return False


def _try_request(url: str, timeout: int, verify: bool) -> Tuple[bool, Optional[int], Optional[str]]:
    """尝试 HTTP 请求。

    Args:
        url: URL 地址
        timeout: 超时时间（秒）
        verify: 是否验证 SSL 证书

    Returns:
        (是否成功, 状态码, 错误信息)
    """
    try:
        # 先尝试 HEAD 请求
        resp = requests.head(
            url,
            timeout=timeout,
            headers=HEADERS,
            allow_redirects=True,
            verify=verify,
        )
        if resp.status_code < 400:
            return True, resp.status_code, None

        # HEAD 失败，降级到 GET
        resp = requests.get(
            url,
            timeout=timeout,
            headers=HEADERS,
            stream=True,
            verify=verify,
        )
        resp.close()
        return resp.status_code < 400, resp.status_code, None
    except requests.RequestException as e:
        return False, None, str(e)


def validate_url(url: str, timeout: int = REQUEST_TIMEOUT) -> ValidationResult:
    """校验单个 URL 是否可访问。

    Args:
        url: URL 地址
        timeout: 超时时间（秒）

    Returns:
        校验结果
    """
    # 判断是否需要跳过 SSL 验证
    skip_ssl = _should_skip_ssl_verification(url)

    # 第一次尝试（根据站点配置决定是否验证 SSL）
    ok, code, err = _try_request(url, timeout, verify=not skip_ssl)

    if ok:
        return ValidationResult(url=url, ok=True, status_code=code)

    # SSL 错误降级：跳过证书验证重试
    if err and ("SSL" in err or "certificate" in err):
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        ok2, code2, err2 = _try_request(url, timeout, verify=False)
        if ok2:
            logger.warning(f"SSL 证书不可信但站点可访问: {url[:80]}")
            return ValidationResult(
                url=url, ok=True, status_code=code2, error="SSL证书不受信任(已跳过验证)"
            )
        return ValidationResult(
            url=url, ok=False, status_code=None, error=f"{err} | 跳过SSL后: {err2}"
        )

    return ValidationResult(url=url, ok=False, status_code=code, error=err)


def validate_all_links(max_workers: int = 5) -> Dict[str, Dict[str, ValidationResult]]:
    """并发校验 OFFICIAL_URLS 中所有链接。

    Args:
        max_workers: 最大并发数

    Returns:
        校验结果字典
    """
    results: Dict[str, Dict[str, ValidationResult]] = {}

    # 构建所有需要校验的链接列表
    all_links: List[Tuple[str, str, str]] = []
    for key, urls in OFFICIAL_URLS.items():
        results[key] = {}
        for label, url in urls.items():
            all_links.append((key, label, url))

    logger.info(f"开始并发校验 {len(OFFICIAL_URLS)} 个标讯的 {len(all_links)} 个链接...")

    def validate_single(item: Tuple[str, str, str]) -> Tuple[str, str, ValidationResult]:
        key, label, url = item
        result = validate_url(url)
        return key, label, result

    # 并发执行校验
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(validate_single, item): item for item in all_links}

        for future in as_completed(futures):
            try:
                key, label, result = future.result()
                results[key][label] = result
                status = "✓" if result.ok else f"✗ ({result.error})"
                logger.info(f"  [{key}] {label}: {status}")
            except Exception as e:
                item = futures[future]
                logger.error(f"  校验失败 [{item[0]}] {item[1]}: {e}")

    return results


def print_validation_report(results: Dict[str, Dict[str, ValidationResult]]) -> None:
    """打印链接校验报告。

    Args:
        results: 校验结果字典
    """
    total = 0
    ok_count = 0
    for key, links in results.items():
        for label, info in links.items():
            total += 1
            if info.ok:
                ok_count += 1
            else:
                print(f"  ✗ [{key}] {label}: {info.url[:80]}... => {info.error}")
    print(f"  链接校验完成: {ok_count}/{total} 可访问")


# ============== 页面抓取 ==============


def _fetch_soup(url: str, timeout: int = REQUEST_TIMEOUT) -> Optional[BeautifulSoup]:
    """抓取页面返回 BeautifulSoup。

    Args:
        url: URL 地址
        timeout: 超时时间（秒）

    Returns:
        BeautifulSoup 对象或 None
    """
    skip_ssl = _should_skip_ssl_verification(url)

    for verify in [not skip_ssl, False]:
        try:
            resp = requests.get(url, timeout=timeout, headers=HEADERS, verify=verify)
            resp.raise_for_status()
            if resp.encoding and resp.encoding.lower() != "utf-8":
                resp.encoding = "utf-8"
            if not verify:
                logger.warning(f"SSL 证书不可信但页面抓取成功: {url[:80]}")
            return BeautifulSoup(resp.text, "html.parser")
        except requests.exceptions.SSLError:
            if verify:
                import urllib3

                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                continue
            logger.warning(f"SSL 错误且跳过验证后仍失败: {url}")
            return None
        except requests.RequestException as e:
            if verify:
                logger.warning(f"抓取失败 {url}: {e}")
                return None
            logger.warning(f"抓取最终失败 {url}: {e}")
            return None
    return None


def _normalize_url(href: str, base_url: str) -> str:
    """将相对链接转为绝对链接。

    Args:
        href: 原始链接
        base_url: 基础 URL

    Returns:
        绝对 URL
    """
    if not href:
        return ""
    href = href.strip()
    if href.startswith(("http://", "https://")):
        return href
    if href.startswith("//"):
        return "https:" + href
    return urljoin(base_url, href)


# ============== 列表页爬取 ==============


# 孟加拉数字 → ASCII 数字映射
_BENGALI_DIGITS = str.maketrans(
    "০১২৩৪৫৬৭৮৯", "0123456789"
)


def _bengali_to_ascii(text: str) -> str:
    """将孟加拉数字转换为 ASCII 数字。

    Args:
        text: 可能包含孟加拉数字的文本

    Returns:
        ASCII 数字文本
    """
    return text.translate(_BENGALI_DIGITS)


def _scrape_table_rows(soup: BeautifulSoup, base_url: str) -> List[ScrapedEntry]:
    """策略1：从 HTML 表格提取标讯条目。

    孟加拉政府门户模板列序：序号 | 标题 | 招标编号 | 类型 | 文件(PDF) | 日期 | 操作(详情页)
    - Col1 (index 1): 标题
    - Col3: 类型 (如 "আন্তর্জাতিক NOA" = International NOA)
    - Col4: PDF 文件链接（不取这个）
    - Col5: 发布日期（孟加拉数字）
    - Col6: 详情页链接（"দেখুন" 按钮）

    Args:
        soup: BeautifulSoup 对象
        base_url: 基础 URL

    Returns:
        标讯条目列表
    """
    entries: List[ScrapedEntry] = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        for row in rows[1:]:
            cols = row.find_all(["td", "th"])
            if len(cols) < 5:
                continue

            # 标题：Col1（有时序号和标题合并，需容错）
            title = cols[1].get_text(" ", strip=True)
            title_col_idx = 1
            # 第2列可能是序号（如"১"），真正的标题在 Col2
            if title and _bengali_to_ascii(title).strip().isdigit():
                if len(cols) > 2:
                    title = cols[2].get_text(" ", strip=True)
                    title_col_idx = 2

            # 跳过空标题行
            if not title or len(title) < 5:
                continue

            # 链接：取最后一列的 <a> 标签（Col6 的 "দেখুন" 详情页链接）
            # 不用 row.find("a") 因为第一个 a 是 Col4 的 PDF 下载链接
            all_links = row.find_all("a", href=True)
            href = ""
            if all_links:
                href = cast(str, all_links[-1]["href"])  # 取最后一个链接 = 详情页

            # 日期：Col5（孟加拉数字格式，如 "১৪-০৫-২০২৬" → "14-05-2026"）
            date_text = ""
            if len(cols) > 5:
                raw_date = cols[5].get_text(strip=True)
                date_text = _bengali_to_ascii(raw_date)

            # 备用：如果 Col5 是空的，尝试其他列
            if not date_text and len(cols) > 4:
                raw_date = cols[4].get_text(strip=True)
                date_text = _bengali_to_ascii(raw_date)

            # 招标类型（Col3），用于标记 NOA
            tender_type = ""
            if len(cols) > 3:
                tender_type = cols[3].get_text(strip=True)

            # 招标编号（Col2）
            tender_no = ""
            if len(cols) > 2:
                tender_no = cols[2].get_text(strip=True)

            # PDF 链接（Col4 的第一个 <a> 标签）
            pdf_url = ""
            if len(cols) > 4:
                pdf_link = cols[4].find("a", href=True)
                if pdf_link:
                    pdf_url = _normalize_url(cast(str, pdf_link["href"]), base_url)

            entries.append(
                ScrapedEntry(
                    title=title,
                    url=_normalize_url(href, base_url),
                    date_text=date_text,
                    tender_type=tender_type,
                    tender_no=tender_no,
                    pdf_url=pdf_url,
                )
            )
    return entries


def _scrape_link_lists(soup: BeautifulSoup, base_url: str) -> List[ScrapedEntry]:
    """策略2：从链接列表提取标讯条目。

    Args:
        soup: BeautifulSoup 对象
        base_url: 基础 URL

    Returns:
        标讯条目列表
    """
    entries: List[ScrapedEntry] = []
    seen: set = set()
    for tag in soup.find_all(["a"], href=True):
        href = cast(str, tag["href"])
        if not href or href == "#":
            continue
        text = tag.get_text(" ", strip=True)
        if not text or len(text) < 10:
            continue
        # 过滤明显非标讯链接
        lower = (text + href).lower()
        if not any(kw in lower for kw in ["tender", "招标", "procurement", "notice", "bid", "noa"]):
            continue
        url = _normalize_url(href, base_url)
        if url in seen:
            continue
        seen.add(url)
        entries.append(ScrapedEntry(title=text, url=url, date_text=""))
    return entries


def _scrape_cards(soup: BeautifulSoup, base_url: str) -> List[ScrapedEntry]:
    """策略3：从卡片/区块提取标讯条目。

    Args:
        soup: BeautifulSoup 对象
        base_url: 基础 URL

    Returns:
        标讯条目列表
    """
    entries: List[ScrapedEntry] = []
    seen: set = set()
    card_classes = ["tender", "notice", "card", "post", "article", "item", "entry", "listing"]
    for tag in soup.find_all(["div", "article", "li", "section"]):
        class_attr = tag.get("class")
        if isinstance(class_attr, list):
            cls = " ".join(str(c) for c in class_attr).lower()
        elif class_attr is None:
            cls = ""
        else:
            cls = str(class_attr).lower()
        if not any(c in cls for c in card_classes):
            continue
        link = tag.find("a", href=True)
        href = cast(str, link["href"]) if link else ""
        title_el = tag.find(["h2", "h3", "h4", "strong", "b"])
        title = (
            title_el.get_text(" ", strip=True) if title_el else tag.get_text(" ", strip=True)[:200]
        )
        if not title or len(title) < 10:
            continue
        url = _normalize_url(href, base_url)
        if url in seen:
            continue
        seen.add(url)
        entries.append(ScrapedEntry(title=title, url=url, date_text=""))
    return entries


def scrape_listing(source_name: str, url: str) -> List[ScrapedEntry]:
    """爬取单个来源的标讯列表页，返回条目列表。

    Args:
        source_name: 来源名称
        url: 列表页 URL

    Returns:
        标讯条目列表
    """
    logger.info(f"正在爬取 {source_name}: {url}")
    soup = _fetch_soup(url)
    if not soup:
        return []

    # 来源→公司推断
    SOURCE_COMPANY_HINT = {
        "BAPEX": "BAPEX",
        "BAPEX_NOA": "BAPEX",
        "SGFL": "SGFL",
        "BGFCL_portal": "BGFCL",
    }

    for strategy, name in [
        (_scrape_table_rows, "表格"),
        (_scrape_link_lists, "链接列表"),
        (_scrape_cards, "卡片区块"),
    ]:
        entries = strategy(soup, url)
        if entries:
            # 标注来源公司
            hint = SOURCE_COMPANY_HINT.get(source_name)
            for entry in entries:
                if hint and not entry.company:
                    entry.company = hint
            logger.info(f"  {source_name}: 通过「{name}」策略找到 {len(entries)} 条标讯")
            return entries

    logger.info(f"  {source_name}: 未找到标讯条目")
    return []


def scrape_all_listings(max_workers: int = 3) -> Dict[str, List[ScrapedEntry]]:
    """并发爬取所有已知来源的标讯列表页。

    Args:
        max_workers: 最大并发数

    Returns:
        按来源分类的标讯条目字典
    """
    all_entries: Dict[str, List[ScrapedEntry]] = {}

    logger.info(f"开始并发爬取 {len(LISTING_URLS)} 个来源的标讯列表...")

    def scrape_single(item: Tuple[str, str]) -> Tuple[str, List[ScrapedEntry]]:
        name, url = item
        entries = scrape_listing(name, url)
        return name, entries

    # 并发执行爬取
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(scrape_single, item): item for item in LISTING_URLS.items()}

        for future in as_completed(futures):
            try:
                name, entries = future.result()
                all_entries[name] = entries
                logger.info(f"  {name}: 爬取完成，获得 {len(entries)} 条标讯")
            except Exception as e:
                item = futures[future]
                logger.error(f"  爬取失败 {item[0]}: {e}")
                all_entries[item[0]] = []

    return all_entries


# ============== 详情页数据提取 ==============


def _parse_date(text: str) -> Optional[datetime]:
    """尝试从文本提取日期。

    使用 dateutil.parser 进行智能日期解析，优先按日-月-年解析
    （适配孟加拉政府网站常见的 DD-MM-YYYY 格式）。

    Args:
        text: 包含日期的文本

    Returns:
        datetime 对象或 None
    """
    if not text:
        return None

    # 先尝试 dateutil 的智能解析（孟加拉网站多为 dayfirst）
    try:
        parsed = date_parser.parse(text, fuzzy=True, dayfirst=True)
        if isinstance(parsed, datetime):
            return parsed
    except (ValueError, TypeError):
        pass

    # 回退到正则匹配（优先日-月-年，再月-日-年）
    patterns = [
        (r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", "%Y-%m-%d"),
        (r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", "%d-%m-%Y"),  # 孟加拉常见 DD-MM-YYYY
        (
            r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[,\s]+(\d{4})",
            "%d %b %Y",
        ),
        (
            r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{1,2}),?\s+(\d{4})",
            "%b %d %Y",
        ),
    ]

    for pattern, fmt in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                groups = m.groups()
                if len(groups) == 3:
                    if fmt.startswith("%d"):
                        return datetime.strptime(f"{groups[0]} {groups[1]} {groups[2]}", fmt)
                    elif fmt.startswith("%b"):
                        return datetime.strptime(f"{groups[0]} {groups[1]} {groups[2]}", fmt)
                    else:
                        return datetime.strptime(
                            f"{groups[0]}-{int(groups[1]):02d}-{int(groups[2]):02d}", "%Y-%m-%d"
                        )
            except ValueError:
                continue

    return None


def scrape_detail_page(url: str) -> Optional[Dict[str, Any]]:
    """尝试从详情页提取标讯结构化数据。

    Args:
        url: 详情页 URL

    Returns:
        标讯数据字典或 None
    """
    soup = _fetch_soup(url)
    if not soup:
        return None

    data: Dict[str, Any] = {"url": url}

    # 标题
    for tag_name in ["h1", "h2", "h3"]:
        h = soup.find(tag_name)
        if h and len(h.get_text(strip=True)) > 5:
            data["title"] = h.get_text(strip=True)
            break
    if "title" not in data:
        title_tag = soup.find("title")
        if title_tag:
            data["title"] = title_tag.get_text(strip=True)

    # 表格数据（键值对）
    fields: Dict[str, str] = {}
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cols = row.find_all(["td", "th"])
            if len(cols) >= 2:
                key = cols[0].get_text(strip=True).rstrip(":")
                val = cols[1].get_text(" ", strip=True)
                if key and val and len(key) < 80:
                    fields[key] = val

    data["fields"] = fields

    # 日期提取（支持多语言字段名）
    all_text = soup.get_text(" ", strip=True)
    date_field_names = [
        # 英文/中文
        ("Publish Date", "发布日期"),
        ("Published Date", "发布日期"),
        ("Closing Date", "截止日期"),
        ("截止日期", "截止日期"),
        ("Deadline", "截止日期"),
        ("Submission Date", "投标截止日期"),
        # 孟加拉语
        ("প্রকাশের তারিখ", "发布日期"),  # Publish Date
        ("আর্কাইভ তারিখ", "存档日期"),    # Archive Date - NOT a tender deadline
        ("দরপত্র জমাদানের শেষ তারিখ", "截止日期"),  # Tender submission deadline
        ("সমাপ্তির তারিখ", "截止日期"),  # Completion/Closing Date
    ]
    for source_name, target_name in date_field_names:
        if source_name in fields:
            dt = _parse_date(fields[source_name])
            if dt:
                data[f"parsed_{target_name}"] = dt.isoformat()

    # 提取标题/描述字段（用于补充采购内容）
    # শিরোনাম = 标题, বিষয় = 主题, দরপত্রের বিবরণ = 招标描述
    desc_fields = ["শিরোনাম", "বিষয়", "দরপত্রের বিবরণ", "Subject", "Description"]
    for df in desc_fields:
        if df in fields and fields[df]:
            val = fields[df].strip()
            # 如果值有意义且不同于页面标题
            if len(val) > 10 and val != data.get("title", ""):
                data["parsed_描述"] = val
                break

    # 全文搜索日期（作为后备）
    if "parsed_截止日期" not in data and "parsed_投标截止日期" not in data:
        dt = _parse_date(all_text[:2000])
        if dt:
            data["parsed_first_date"] = dt.isoformat()

    return data


# ============== PDF 解析 ==============


def _download_pdf_bytes(pdf_url: str) -> Optional[bytes]:
    """下载 PDF 文件内容。

    Args:
        pdf_url: PDF 文件 URL

    Returns:
        PDF 字节内容或 None
    """
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    try:
        resp = requests.get(pdf_url, headers=HEADERS, verify=False, timeout=45)
        resp.raise_for_status()
        return resp.content
    except requests.RequestException as e:
        logger.warning(f"PDF 下载失败 {pdf_url[:80]}: {e}")
        return None


def _is_scanned_pdf(pdf_bytes: bytes) -> bool:
    """检测 PDF 是否为扫描件（无可提取文本）。

    Args:
        pdf_bytes: PDF 字节内容

    Returns:
        True 表示是扫描件
    """
    import io

    try:
        import fitz

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_text = ""
        for page in doc:
            total_text += page.get_text()
        doc.close()
        # 如果所有页面总文本 < 50 字符，判定为扫描件
        return len(total_text.strip()) < 50
    except Exception:
        return True


def _extract_pdf_text(pdf_bytes: bytes) -> Optional[str]:
    """从 PDF 字节中提取全部文本。

    Args:
        pdf_bytes: PDF 字节内容

    Returns:
        提取的文本或 None
    """
    import io

    try:
        import fitz

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        texts = []
        for page in doc:
            texts.append(page.get_text())
        doc.close()
        return "\n".join(texts)
    except Exception as e:
        logger.warning(f"PDF 文本提取失败: {e}")
        return None


def _clean_pdf_text(text: str) -> str:
    """清理 PDF 提取文本中的乱码字符。

    孟加拉 PDF 文本常混有 Unicode 组合字符和 OCR 噪声。
    清理后保留英文、数字、标点、空格和换行。

    Args:
        text: 原始 PDF 文本

    Returns:
        清理后的文本
    """
    import unicodedata

    # 规范化 Unicode
    text = unicodedata.normalize("NFKD", text)
    # 保留可打印 ASCII + 换行
    cleaned = []
    for ch in text:
        if ch == "\n" or ch == "\r":
            cleaned.append("\n")
        elif 32 <= ord(ch) <= 126:
            cleaned.append(ch)
        elif ord(ch) == 9:  # tab
            cleaned.append(" ")
    return "".join(cleaned)


def _parse_money_amounts(text: str) -> Dict[str, str]:
    """从 PDF 文本中提取货币金额。

    识别模式：USD/BDT + 数字（孟加拉数字格式如 1,00,00,000.00）

    Args:
        text: 清理后的 PDF 文本

    Returns:
        {"USD": "63,622,027.00", "BDT": "131,00,00,000.00", ...}
    """
    amounts: Dict[str, str] = {}
    # 孟加拉金额格式（lakh/crore）
    money_pattern = re.compile(
        r"(USD|BDT|US\s*Doll[ae]r|Bangladeshi\s*Taka)\s+"
        r"([\d,]+\.?\d*)",
        re.IGNORECASE,
    )
    for m in money_pattern.finditer(text):
        currency = m.group(1).upper().strip()
        value = m.group(2)
        if "DOLLAR" in currency or "USD" in currency:
            amounts["USD"] = value
        elif "TAKA" in currency or "BDT" in currency:
            amounts["BDT"] = value
    return amounts


def _parse_deadline(text: str) -> Optional[datetime]:
    """从 PDF 文本中提取截止日期。

    搜索 Closing Date / Deadline / Submission 附近日期。

    Args:
        text: 清理后的 PDF 文本

    Returns:
        datetime 或 None
    """
    patterns = [
        # "Closing Date: 18 May 2026"
        r"(?:Closing|Deadline|Submission)\s*Date[:\s]+(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})",
        # "closing date: 18-05-2026"
        r"(?:closing|deadline|submission)\s*date[:\s]+(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})",
        # "not later than 18 May 2026"
        r"not\s+later\s+than\s+(\d{1,2}\s+\w+\s+\d{4})",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            date_str = m.group(1)
            dt = _parse_date(date_str)
            if dt:
                return dt
    return None


def _ocr_pdf_bytes(pdf_bytes: bytes, dpi: int = 250) -> Optional[str]:
    """对 PDF 字节进行 OCR 文字识别。

    Args:
        pdf_bytes: PDF 文件字节内容
        dpi: 渲染分辨率

    Returns:
        OCR 识别文本或 None
    """
    try:
        import io as _io

        import fitz
        from PIL import Image

        import pytesseract

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        texts = []
        for page_num in range(min(doc.page_count, 5)):  # 最多处理5页
            page = doc[page_num]
            # 先尝试直接提取文本
            native = page.get_text().strip()
            if native and len(native) > 50:
                texts.append(native)
                continue
            # 渲染为图片做 OCR
            pix = page.get_pixmap(dpi=dpi)
            img = Image.open(_io.BytesIO(pix.tobytes("png")))
            ocr_text = pytesseract.image_to_string(img, lang="eng")
            if ocr_text.strip():
                texts.append(ocr_text)
        doc.close()
        return "\n".join(texts) if texts else None
    except ImportError as e:
        logger.warning(f"OCR 依赖缺失: {e}")
        return None
    except Exception as e:
        logger.warning(f"OCR 识别失败: {e}")
        return None


def _extract_ocr_fields(text: str) -> Dict[str, Any]:
    """从 OCR 文本中提取标讯关键字段。

    Args:
        text: OCR 识别文本

    Returns:
        提取的字段字典
    """
    result: Dict[str, Any] = {}
    # 规范化空格
    clean = re.sub(r"\s+", " ", text)

    # ---- 截止日期 (Tender Closing Date and Time) ----
    # OCR 中日期和时间之间可能有 | 或多种分隔符
    closing_patterns = [
        r"Tender\s*Closing\s*Date\s*(?:and|&)\s*Time[:\s|]*(\d{1,2}[-/]\d{1,2}[-/]\d{4})\s*\|?\s*(\d{1,2}[.:]\d{2})",
        r"Closing\s*Date\s*(?:and|&)\s*Time[:\s|]*(\d{1,2}[-/]\d{1,2}[-/]\d{4})\s*\|?\s*(\d{1,2}[.:]\d{2})",
        r"Closing\s*Date[:\s]*(\d{1,2}[-/]\d{1,2}[-/]\d{4})\s*\|?\s*(\d{1,2}[.:]\d{2})",
        r"Tender\s*Closing\s*Date[:\s]*(\d{1,2}[-/]\d{1,2}[-/]\d{4})\s*\|?\s*(\d{1,2}[.:]\d{2})",
    ]
    for pattern in closing_patterns:
        m = re.search(pattern, clean, re.IGNORECASE)
        if m:
            date_str = m.group(1)
            time_str = m.group(2) if m.lastindex and m.lastindex >= 2 else "00:00"
            # OCR 常用点号代替冒号
            time_str = time_str.replace(".", ":")
            dt = _parse_date(f"{date_str} {time_str}")
            if dt:
                result["deadline"] = dt.isoformat()
            break

    # ---- 标书价格 (Price of Tender Document) ----
    price_match = re.search(
        r"Price\s*(?:of|:)?\s*Tender\s*Document[:\s]*.*?(BDT\s*[\d,]+(?:[.]\d{2})?).*?(USD\s*[\d,]+(?:[.]\d{2})?)",
        clean, re.IGNORECASE,
    )
    if price_match:
        if price_match.group(1):
            result["bdt_amount"] = re.sub(r"[^\d.]", "", price_match.group(1))
        if price_match.lastindex and price_match.lastindex >= 2 and price_match.group(2):
            result["usd_amount"] = re.sub(r"[^\d.]", "", price_match.group(2))

    # ---- 投标保证金 (Tender Security) ----
    security_match = re.search(
        r"Tender\s*Security[:\s]*.*?(USD\s*[\d,]+(?:[.]\d{2})?)",
        clean, re.IGNORECASE,
    )
    if security_match:
        result["security_usd"] = security_match.group(1).strip()

    # ---- 招标编号 ----
    tn_patterns = [
        r"(?:Invitation|Tender)\s*Ref\s*No[.:\s#]*([A-Z0-9/()\-]+(?:/\d{4})?)",
        r"(?:Tender|Invitation)\s*(?:Ref|Reference)\s*(?:No|Number)?[.:\s#]*([A-Z0-9/()\-]+(?:/\d{4})?)",
        r"Tender\s*(?:Package\s*)?No[.:\s#]*-?[.:\s#]*([A-Z0-9/()\-]+(?:/\d{4})?)",
    ]
    for pattern in tn_patterns:
        m = re.search(pattern, clean, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            # 过滤掉明显的误匹配（如 "No"、"FUNDING" 等）
            if candidate.upper() not in ("NO", "FUNDING", "INFORMATION", "KEY", "DATE", "TIME"):
                result["tender_no_from_pdf"] = candidate
                break

    # ---- 采购方式 ----
    method_match = re.search(
        r"Procurement\s*Method[:\s]*(.{5,80}?)(?:\s*\d+\s*\||\s*FUNDING|\s*\n\s*\d)",
        clean, re.IGNORECASE,
    )
    if method_match:
        method = method_match.group(1).strip()
        # 清理 OCR 噪音
        method = re.sub(r"\s{2,}", " ", method)
        method = re.sub(r"^\[?_?", "", method)  # 去掉 OCR 伪影
        if len(method) > 5 and "FUNDING" not in method[:50]:
            result["procurement_method"] = method[:200]

    # ---- 投标资格 (Eligibility): 查找有实质资格要求的段落 ----
    # 策略1：从 "Brief Eligibility" 或 "qualification" 关键词后的英文段落
    elig_match = re.search(
        r"(?:Brief\s*Eligibility[^.]*?\.|qualification\s*(?:of|criteria))[:\s]*(.{30,400}?)(?:\s*\d+\s*[|_]\s*|\s*Price\s*of\s*Tender)",
        clean, re.IGNORECASE,
    )
    if elig_match:
        elig_text = elig_match.group(1).strip()
        # 清理
        elig_text = re.sub(r"^\s*[°•▪▸]\s*", "", elig_text)  # 去掉开头符号
        elig_text = re.sub(r"^of\s+", "", elig_text)  # 去掉开头 of
        elig_text = re.sub(r"The\s*minimum\s*of\s*years\b", "The minimum years", elig_text)
        if len(elig_text) > 20:
            result["eligibility"] = elig_text[:400]
    else:
        # 策略2：找包含 experience/track record 的段落
        elig_match2 = re.search(
            r"(?:experience|track\s*record).{30,300}?(?:years?\.|experience\.)",
            clean, re.IGNORECASE,
        )
        if elig_match2:
            elig_text = elig_match2.group(0).strip()[:400]
            if "As per Tender Document" not in elig_text:
                result["eligibility"] = elig_text

    # ---- 投标有效期 ----
    validity_match = re.search(
        r"(?:Tender|Bid)\s*Validity\s*(?:Period)?[:\s]*(\d+)\s*(?:days|Days)",
        clean, re.IGNORECASE,
    )
    if validity_match:
        result["validity_days"] = int(validity_match.group(1))

    # ---- 交货期/合同期 ----
    completion_match = re.search(
        r"Completion\s*(?:Time|Period)[:\s/]*.*?(\d+)\s*(?:\([^)]*\))?\s*(?:months|Months|days|Days)",
        clean, re.IGNORECASE,
    )
    if completion_match:
        result["completion_time"] = completion_match.group(0).strip()[:100]

    # ---- 联系人 ----
    name_match = re.search(
        r"Name\s*of\s*Official\s*(?:Inviting\s*Tender)?[:\s]*([A-Z][a-z]+(?:\s+[A-Z][a-z.]+)+)",
        clean,
    )
    if name_match:
        person = name_match.group(1).strip()
        # 清理多余的 OCR 噪音词
        for noise in ("Inviting Tender", "Designation", "Address"):
            person = person.replace(noise, "").strip()
        if person:
            result["contact_person"] = person

    # ---- 项目名称 ----
    proj_match = re.search(
        r"Project\s*Name[:\s]*(.{10,200}?)(?:Tender\s*Package|Tender\s*Publication|\d+\s*[|_])",
        clean, re.IGNORECASE,
    )
    if proj_match:
        proj = proj_match.group(1).strip()
        if len(proj) > 10:
            result["project_name"] = proj[:300]

    # ---- 标书发售截止 ----
    selling_match = re.search(
        r"(?:Tender\s*)?Last\s*Selling\s*Date[:\s]*(\d{1,2}[-/]\d{1,2}[-/]\d{4})",
        clean, re.IGNORECASE,
    )
    if selling_match:
        result["last_selling_date"] = selling_match.group(1).strip()

    return result


def parse_pdf_fields(pdf_url: str) -> Dict[str, Any]:
    """解析单个 PDF 文件，提取关键字段（含 OCR 回退）。

    Args:
        pdf_url: PDF 文件 URL

    Returns:
        {"deadline": datetime, "usd_amount": str, "bdt_amount": str, "is_scanned": bool, ...}
    """
    result: Dict[str, Any] = {"pdf_url": pdf_url, "is_scanned": False, "error": None}

    pdf_bytes = _download_pdf_bytes(pdf_url)
    if not pdf_bytes:
        result["error"] = "下载失败"
        return result

    is_scanned = _is_scanned_pdf(pdf_bytes)
    result["is_scanned"] = is_scanned

    raw_text = _extract_pdf_text(pdf_bytes)

    # 扫描件或无文本 → 尝试 OCR
    if is_scanned or not raw_text:
        ocr_text = _ocr_pdf_bytes(pdf_bytes)
        if ocr_text:
            result["ocr_text"] = ocr_text[:8000]
            ocr_fields = _extract_ocr_fields(ocr_text)
            result.update(ocr_fields)
            if ocr_fields:
                result["source"] = "ocr"
                return result

        result["error"] = "OCR 识别失败" if is_scanned else "文本提取失败"
        return result

    cleaned = _clean_pdf_text(raw_text)
    result["raw_text"] = cleaned[:5000]

    # 金额
    amounts = _parse_money_amounts(cleaned)
    result.update(amounts)

    # 截止日期
    deadline = _parse_deadline(cleaned)
    if deadline:
        result["deadline"] = deadline.isoformat()

    # 招标编号
    tn_pattern = re.search(
        r"(?:Tender|TENDER)\s*(?:No|NO|Reference)[:\s#]*([A-Z0-9/()\-.]+(?:\s*dated[:\s]*[\d\-./]+)?)",
        cleaned,
        re.IGNORECASE,
    )
    if tn_pattern:
        result["tender_no_from_pdf"] = tn_pattern.group(1).strip()

    return result
