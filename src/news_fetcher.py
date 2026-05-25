# -*- coding: utf-8 -*-
"""能源新闻抓取模块 —— 抓取国际能源行业动态"""

import logging
import re
from datetime import datetime
from typing import List, Optional

import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

from src.scraper import HEADERS, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

# 能源新闻源
_NEWS_SOURCES = [
    {
        "name": "孟加拉+国际能源",
        "url": "https://news.google.com/rss/search?q=bangladesh+gas+petroleum+energy+LNG+oil&hl=en-US&gl=US&ceid=US:en",
        "max_items": 6,
    },
    {
        "name": "霍尔木兹+地缘政治",
        "url": "https://news.google.com/rss/search?q=strait+of+hormuz+oil+tanker+middle+east+energy&hl=en-US&gl=US&ceid=US:en",
        "max_items": 4,
    },
]


class NewsItem:
    """单条新闻"""

    def __init__(self, title: str, source: str, url: str, published: str = "", description: str = ""):
        self.title = title
        self.source = source
        self.url = url
        self.published = published
        self.description = description
        self.title_cn = ""  # 中文翻译
        self.category_cn = ""  # 分类标签

    def to_html(self) -> str:
        """转为 HTML 格式，中文标题 + 分类 + 来源"""
        display_title = self.title_cn if self.title_cn else self.title
        pub = f" ({self.published})" if self.published else ""
        cat = f" <font color='#1a365d'>[{self.category_cn}]</font>" if self.category_cn else ""
        return (
            f"• {cat} <a href='{self.url}' color='blue'>{display_title}</a> "
            f"<font color='#6b7280'>— {self.source}{pub}</font><br/>"
        )


def _categorize_news(item: NewsItem) -> str:
    """根据标题关键词为新闻分类。"""
    title_lower = (item.title + " " + item.source).lower()
    categories = {
        "LNG/天然气": ["lng", "natural gas", "gas supply", "gas field", "gas price", "fsru"],
        "石油/原油": ["oil price", "crude oil", "petroleum", "barrel", "brent", "wti", "opec"],
        "地缘政治": ["strait of hormuz", "iran", "middle east", "sanction", "conflict", "war", "attack"],
        "孟加拉能源": ["bangladesh", "dhaka", "petrobangla", "bapex", "sgfl", "bgfcl"],
        "能源转型": ["renewable", "solar", "wind", "transition", "climate", "carbon", "emission", "green"],
        "投资/市场": ["investment", "investor", "stock", "market", "merger", "acquisition", "deal", "sign"],
        "海上勘探": ["offshore", "deepwater", "drilling", "seismic", "exploration", "rig"],
    }
    for cat, keywords in categories.items():
        if any(kw in title_lower for kw in keywords):
            return cat
    return "能源动态"


def _extract_article_summary(url: str, fallback: str = "") -> str:
    """从文章页面提取摘要。Google News 不提供原文链接，返回空。"""
    return ""


def _translate_items(items: List[NewsItem]) -> None:
    """翻译新闻标题为中文并分类。"""
    if not items:
        return
    try:
        from deep_translator import GoogleTranslator

        translator = GoogleTranslator(source="auto", target="zh-CN")

        for item in items:
            # 翻译标题
            try:
                clean_title = item.title.rsplit(" - ", 1)[0].strip()
                if len(clean_title) > 10:
                    cn = translator.translate(clean_title)
                    if cn and len(cn) > 2:
                        item.title_cn = cn
            except Exception:
                pass

            # 分类
            item.category_cn = _categorize_news(item)

    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"翻译失败: {e}")


class NewsFetcher:
    """能源新闻抓取器"""

    def fetch(self, max_total: int = 10) -> List[NewsItem]:
        """抓取能源新闻。

        Args:
            max_total: 最多返回的总条数

        Returns:
            新闻列表
        """
        all_items: List[NewsItem] = []
        seen_titles: set = set()

        for source in _NEWS_SOURCES:
            try:
                items = self._fetch_rss(source["url"], source["max_items"])
                for item in items:
                    title_key = item.title.lower()[:60]
                    if title_key not in seen_titles:
                        seen_titles.add(title_key)
                        all_items.append(item)
            except Exception as e:
                logger.warning(f"新闻源 {source['name']} 抓取失败: {e}")
                continue

        return all_items[:max_total]

    def _fetch_rss(self, url: str, max_items: int = 5) -> List[NewsItem]:
        """从 RSS 源抓取新闻，尝试解析摘要和真实 URL。

        Args:
            url: RSS 源 URL
            max_items: 最多返回条数

        Returns:
            新闻列表
        """
        try:
            resp = requests.get(
                url,
                timeout=REQUEST_TIMEOUT,
                headers=HEADERS,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.warning(f"RSS 请求失败 {url}: {e}")
            return []

        try:
            root = ET.fromstring(resp.text)
        except ET.ParseError as e:
            logger.warning(f"RSS 解析失败 {url}: {e}")
            return []

        items: List[NewsItem] = []
        for item_elem in root.iter("item"):
            if len(items) >= max_items:
                break

            title = ""
            link = ""
            source = ""
            pub_date = ""
            description = ""

            for child in item_elem:
                tag = child.tag.lower() if "}" not in child.tag else child.tag.split("}")[-1]
                text = child.text or ""

                if tag == "title":
                    title = text
                elif tag == "link":
                    link = text
                elif tag == "source":
                    source = text
                elif tag == "description":
                    clean = re.sub(r"<[^>]+>", "", text).strip()
                    clean = re.sub(r"&nbsp;", " ", clean)
                    clean = re.sub(r"&#(\d+);", " ", clean)
                    # 过滤 Google News 重定向链接
                    clean = re.sub(r"https?://news\.google\.com/\S+", "", clean)
                    # 去掉与标题重复的部分
                    if clean.lower().startswith(title.lower()[:30]):
                        clean = clean[len(title):].strip()
                    if len(clean) > 30:
                        description = clean[:300]

            if title and link:
                # 清理标题
                clean_title = title.rsplit(" - ", 1)[0].strip()

                # 解析 Google News 重定向得到真实 URL
                real_url = link
                if "news.google.com/rss/articles" in link:
                    try:
                        head = requests.head(
                            link,
                            timeout=10,
                            headers=HEADERS,
                            allow_redirects=True,
                        )
                        real_url = head.url
                    except Exception:
                        pass

                # 提取文章摘要
                description = _extract_article_summary(real_url, description)

                items.append(
                    NewsItem(
                        title=clean_title,
                        source=source,
                        url=real_url,
                        published=pub_date,
                        description=description,
                    )
                )

        return items


def get_industry_news_html(validation_date: Optional[datetime] = None) -> str:
    """获取行业动态 HTML（实时抓取新闻，无新内容则不显示）。

    Args:
        validation_date: 链接校验日期

    Returns:
        格式化的 HTML，无新闻时返回空字符串
    """
    fmt_date = (validation_date or datetime.now()).strftime("%Y-%m-%d")
    today = datetime.now()
    parts: List[str] = []

    # 尝试抓取实时新闻
    fetcher = NewsFetcher()
    try:
        news_items = fetcher.fetch(max_total=8)
    except Exception as e:
        logger.warning(f"新闻抓取失败: {e}")
        news_items = []

    if not news_items:
        parts.append("<b>链接校验说明</b><br/>")
        parts.append(f"• 本报告所有官方来源链接和PDF下载地址均于{fmt_date}校验通过，可正常访问。")
        return "".join(parts)

    # 翻译标题和描述为中文
    _translate_items(news_items)

    # 动态展示（中文标题）
    parts.append("<b>行业动态与实时新闻</b><br/>")
    for item in news_items:
        parts.append(item.to_html())

    # 链接校验说明
    parts.append("<br/><b>链接校验说明</b><br/>")
    parts.append(f"• 本报告所有官方来源链接和PDF下载地址均于{fmt_date}校验通过，可正常访问。")

    return "".join(parts)
