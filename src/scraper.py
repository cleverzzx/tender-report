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


def _scrape_table_rows(soup: BeautifulSoup, base_url: str) -> List[ScrapedEntry]:
    """策略1：从 HTML 表格提取标讯条目。

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
            if len(cols) < 2:
                continue
            link = row.find("a", href=True)
            href = cast(str, link["href"]) if link else ""
            entries.append(
                ScrapedEntry(
                    title=cols[-1].get_text(" ", strip=True),
                    url=_normalize_url(href, base_url),
                    date_text=cols[0].get_text(strip=True) if cols else "",
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
        if not any(kw in lower for kw in ["tender", "招标", "procurement", "notice", "bid"]):
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

    使用 dateutil.parser 进行智能日期解析。

    Args:
        text: 包含日期的文本

    Returns:
        datetime 对象或 None
    """
    if not text:
        return None

    # 先尝试 dateutil 的智能解析
    try:
        parsed = date_parser.parse(text, fuzzy=True)
        if isinstance(parsed, datetime):
            return parsed
    except (ValueError, TypeError):
        pass

    # 回退到正则匹配
    patterns = [
        (r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", "%Y-%m-%d"),
        (r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", "%m-%d-%Y"),
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

    # 日期提取
    all_text = soup.get_text(" ", strip=True)
    date_fields = [
        "Publish Date",
        "Published Date",
        "发布日期",
        "Closing Date",
        "截止日期",
        "Deadline",
    ]
    for f in date_fields:
        if f in fields:
            dt = _parse_date(fields[f])
            if dt:
                data[f"parsed_{f}"] = dt.isoformat()

    # 全文搜索日期
    if "parsed_日期" not in data:
        dt = _parse_date(all_text[:2000])
        if dt:
            data["parsed_first_date"] = dt.isoformat()

    return data
