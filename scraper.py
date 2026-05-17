# -*- coding: utf-8 -*-
"""标讯爬虫模块 —— 链接校验 + 列表页爬取 + 详情页数据提取"""

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from src.urls import LISTING_URLS, OFFICIAL_URLS

logger = logging.getLogger(__name__)

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


# ============== 链接校验 ==============

def _try_request(url, timeout, verify):
    """尝试 HEAD 请求，失败则降级到 GET。"""
    try:
        resp = requests.head(
            url, timeout=timeout, headers=HEADERS,
            allow_redirects=True, verify=verify,
        )
        if resp.status_code < 400:
            return True, resp.status_code, None
        resp = requests.get(
            url, timeout=timeout, headers=HEADERS,
            stream=True, verify=verify,
        )
        resp.close()
        return resp.status_code < 400, resp.status_code, None
    except requests.RequestException as e:
        return False, None, str(e)


def validate_url(url, timeout=REQUEST_TIMEOUT):
    """校验单个 URL 是否可访问，返回 (ok, status_code, error)。
    SSL 证书问题会降级重试（部分政府网站证书链不完整）。"""
    ok, code, err = _try_request(url, timeout, verify=True)
    if ok:
        return True, code, None

    # SSL 错误降级：跳过证书验证重试
    if err and ("SSL" in err or "certificate" in err):
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        ok2, code2, err2 = _try_request(url, timeout, verify=False)
        if ok2:
            logger.warning("SSL 证书不可信但站点可访问: %s", url[:80])
            return True, code2, "SSL证书不受信任(已跳过验证)"
        return False, None, f"{err} | 跳过SSL后: {err2}"

    return False, code, err


def validate_all_links(max_workers=5):
    """并发校验 OFFICIAL_URLS 中所有链接。"""
    results = {}

    # 构建所有需要校验的链接列表
    all_links = []
    for key, urls in OFFICIAL_URLS.items():
        results[key] = {}
        for label, url in urls.items():
            all_links.append((key, label, url))

    logger.info("开始并发校验 %d 个标讯的 %d 个链接...", len(OFFICIAL_URLS), len(all_links))

    def validate_single(item):
        key, label, url = item
        ok, code, err = validate_url(url)
        return key, label, {"url": url, "ok": ok, "status": code, "error": err}

    # 并发执行校验
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(validate_single, item): item for item in all_links}

        for future in as_completed(futures):
            try:
                key, label, result = future.result()
                results[key][label] = result
                status = "✓" if result["ok"] else f"✗ ({result['error']})"
                logger.info("  [%s] %s: %s", key, label, status)
            except Exception as e:
                item = futures[future]
                logger.error("  校验失败 [%s] %s: %s", item[0], item[1], e)

    return results


def print_validation_report(results):
    """打印链接校验报告。"""
    total = 0
    ok_count = 0
    for key, links in results.items():
        for label, info in links.items():
            total += 1
            if info["ok"]:
                ok_count += 1
            else:
                print(f"  ✗ [{key}] {label}: {info['url'][:80]}... => {info['error']}")
    print(f"  链接校验完成: {ok_count}/{total} 可访问")


# ============== 页面抓取 ==============

def _fetch_soup(url, timeout=REQUEST_TIMEOUT):
    """抓取页面返回 BeautifulSoup，SSL 证书问题会降级重试。"""
    for verify in [True, False]:
        try:
            resp = requests.get(url, timeout=timeout, headers=HEADERS, verify=verify)
            resp.raise_for_status()
            if resp.encoding and resp.encoding.lower() != "utf-8":
                resp.encoding = "utf-8"
            if not verify:
                logger.warning("SSL 证书不可信但页面抓取成功: %s", url[:80])
            return BeautifulSoup(resp.text, "html.parser")
        except requests.exceptions.SSLError:
            if verify:
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                continue
            logger.warning("SSL 错误且跳过验证后仍失败: %s", url)
            return None
        except requests.RequestException as e:
            if verify:
                # 非 SSL 错误不重试
                logger.warning("抓取失败 %s: %s", url, e)
                return None
            logger.warning("抓取最终失败 %s: %s", url, e)
            return None
    return None


def _normalize_url(href, base_url):
    """将相对链接转为绝对链接。"""
    if not href:
        return ""
    href = href.strip()
    if href.startswith(("http://", "https://")):
        return href
    if href.startswith("//"):
        return "https:" + href
    return urljoin(base_url, href)


# ============== 列表页爬取 ==============

def _scrape_table_rows(soup, base_url):
    """策略1：从 HTML 表格提取标讯条目。"""
    entries = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        for row in rows[1:]:
            cols = row.find_all(["td", "th"])
            if len(cols) < 2:
                continue
            link = row.find("a", href=True)
            entries.append({
                "title": cols[-1].get_text(" ", strip=True),
                "url": _normalize_url(link["href"], base_url) if link else "",
                "date_text": cols[0].get_text(strip=True) if cols else "",
            })
    return entries


def _scrape_link_lists(soup, base_url):
    """策略2：从链接列表提取标讯条目。"""
    entries = []
    seen = set()
    for tag in soup.find_all(["a"], href=True):
        href = tag["href"]
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
        entries.append({"title": text, "url": url, "date_text": ""})
    return entries


def _scrape_cards(soup, base_url):
    """策略3：从卡片/区块提取标讯条目。"""
    entries = []
    seen = set()
    card_classes = ["tender", "notice", "card", "post", "article", "item", "entry", "listing"]
    for tag in soup.find_all(["div", "article", "li", "section"]):
        cls = " ".join(tag.get("class", [])).lower()
        if not any(c in cls for c in card_classes):
            continue
        link = tag.find("a", href=True)
        title_el = tag.find(["h2", "h3", "h4", "strong", "b"])
        title = title_el.get_text(" ", strip=True) if title_el else tag.get_text(" ", strip=True)[:200]
        if not title or len(title) < 10:
            continue
        url = _normalize_url(link["href"], base_url) if link else ""
        if url in seen:
            continue
        seen.add(url)
        entries.append({"title": title, "url": url, "date_text": ""})
    return entries


def scrape_listing(source_name, url):
    """爬取单个来源的标讯列表页，返回条目列表。"""
    logger.info("正在爬取 %s: %s", source_name, url)
    soup = _fetch_soup(url)
    if not soup:
        return []

    for strategy, name in [
        (_scrape_table_rows, "表格"),
        (_scrape_link_lists, "链接列表"),
        (_scrape_cards, "卡片区块"),
    ]:
        entries = strategy(soup, url)
        if entries:
            logger.info("  %s: 通过「%s」策略找到 %d 条标讯", source_name, name, len(entries))
            return entries

    logger.info("  %s: 未找到标讯条目", source_name)
    return []


def scrape_all_listings(max_workers=3):
    """并发爬取所有已知来源的标讯列表页。"""
    all_entries = {}

    logger.info("开始并发爬取 %d 个来源的标讯列表...", len(LISTING_URLS))

    def scrape_single(item):
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
                logger.info("  %s: 爬取完成，获得 %d 条标讯", name, len(entries))
            except Exception as e:
                item = futures[future]
                logger.error("  爬取失败 %s: %s", item[0], e)
                all_entries[item[0]] = []

    return all_entries


# ============== 详情页数据提取 ==============

def _parse_date(text):
    """尝试从文本提取日期。"""
    patterns = [
        (r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", "%Y-%m-%d"),
        (r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", "%m-%d-%Y"),
        (r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[,\s]+(\d{4})", "%d %b %Y"),
        (r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{1,2}),?\s+(\d{4})", "%b %d %Y"),
    ]
    for pattern, fmt in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                date_str = " ".join(m.groups()) if " " in fmt else "-".join(m.groups())
                if " " in fmt:
                    return datetime.strptime(date_str, fmt)
                return datetime.strptime(
                    f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}", "%Y-%m-%d"
                )
            except ValueError:
                continue
    return None


def scrape_detail_page(url):
    """尝试从详情页提取标讯结构化数据。"""
    soup = _fetch_soup(url)
    if not soup:
        return None

    data = {"url": url}

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
    fields = {}
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
    date_fields = ["Publish Date", "Published Date", "发布日期", "Closing Date", "截止日期", "Deadline"]
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
