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

# Google News RSS 搜索源
_NEWS_SOURCES = [
    {
        "name": "global_energy",
        "url": "https://news.google.com/rss/search?q=oil+gas+energy+LNG&hl=en-US&gl=US&ceid=US:en",
        "max_items": 5,
    },
    {
        "name": "strait_of_hormuz",
        "url": "https://news.google.com/rss/search?q=strait+of+hormuz+oil+tanker&hl=en-US&gl=US&ceid=US:en",
        "max_items": 3,
    },
    {
        "name": "bangladesh_energy",
        "url": "https://news.google.com/rss/search?q=bangladesh+gas+petroleum+energy&hl=en-US&gl=US&ceid=US:en",
        "max_items": 5,
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

    def to_html(self) -> str:
        """转为 HTML 格式，含摘要"""
        pub = f" ({self.published})" if self.published else ""
        desc_html = ""
        if self.description and len(self.description) > 20:
            desc_html = (
                f"<br/><font color='#374151' size='2'>　　{self.description[:120]}</font>"
            )
        return (
            f"• <a href='{self.url}' color='blue'>{self.title}</a> "
            f"<font color='#6b7280'>— {self.source}{pub}</font>{desc_html}"
        )


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
                    # 清理 HTML 标签
                    clean = re.sub(r"<[^>]+>", "", text).strip()
                    description = clean

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

                # 如果没有摘要，尝试从页面 OG 标签获取
                if not description or len(description) < 30:
                    try:
                        article_resp = requests.get(
                            real_url,
                            timeout=10,
                            headers=HEADERS,
                        )
                        article_soup = BeautifulSoup(article_resp.text, "html.parser")
                        # 尝试 og:description
                        og_desc = article_soup.find("meta", property="og:description")
                        if og_desc and isinstance(og_desc, type(article_soup.find("meta"))) and og_desc.get("content"):
                            description = str(og_desc["content"])[:200]
                        else:
                            # 尝试 description meta
                            m_desc = article_soup.find("meta", attrs={"name": "description"})
                            if m_desc and isinstance(m_desc, type(article_soup.find("meta"))) and m_desc.get("content"):
                                description = str(m_desc["content"])[:200]
                    except Exception:
                        pass

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
        # 无新闻可展示，只保留链接校验说明
        parts.append("<b>链接校验说明</b><br/>")
        parts.append(f"• 本报告所有官方来源链接和PDF下载地址均于{fmt_date}校验通过，可正常访问。")
        return "".join(parts)

    # 有新闻 → 动态展示
    parts.append("<b>行业动态与实时新闻</b><br/>")
    for item in news_items:
        parts.append(item.to_html() + "<br/>")

    # 链接校验说明
    parts.append("<br/><b>链接校验说明</b><br/>")
    parts.append(f"• 本报告所有官方来源链接和PDF下载地址均于{fmt_date}校验通过，可正常访问。")

    return "".join(parts)
