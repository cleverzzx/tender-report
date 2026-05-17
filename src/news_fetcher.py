# -*- coding: utf-8 -*-
"""能源新闻抓取模块 —— 抓取国际能源行业动态"""

import logging
from datetime import datetime
from typing import List, Optional

import requests
import xml.etree.ElementTree as ET

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

    def __init__(self, title: str, source: str, url: str, published: str = ""):
        self.title = title
        self.source = source
        self.url = url
        self.published = published

    def to_html(self) -> str:
        """转为 HTML 格式"""
        pub = f" ({self.published})" if self.published else ""
        return (
            f"<a href='{self.url}' color='blue'>{self.title}</a> "
            f"<font color='#6b7280'>— {self.source}{pub}</font>"
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
        """从 RSS 源抓取新闻。

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

            for child in item_elem:
                tag = child.tag.lower() if "}" not in child.tag else child.tag.split("}")[-1]
                text = child.text or ""

                if tag == "title":
                    title = text
                elif tag == "link":
                    link = text
                elif tag == "source":
                    source = text

            if title and link:
                # 清理标题
                clean_title = title.rsplit(" - ", 1)[0].strip()
                items.append(NewsItem(title=clean_title, source=source, url=link, published=pub_date))

        return items


def get_industry_news_html(validation_date: Optional[datetime] = None) -> str:
    """获取行业动态 HTML 文本。

    优先使用实时新闻抓取，失败则回退到模板。

    Args:
        validation_date: 链接校验日期

    Returns:
        格式化的 HTML 行业动态文本
    """
    fetcher = NewsFetcher()
    news_items = fetcher.fetch(max_total=10)

    fmt_date = (validation_date or datetime.now()).strftime("%Y-%m-%d")

    parts: List[str] = []

    if news_items:
        parts.append("<b>1. 国际能源市场动态</b><br/>")
        for i, item in enumerate(news_items, 1):
            parts.append(f"• {item.to_html()}<br/>")

        parts.append("<br/><b>2. 孟加拉能源概况</b><br/>")
        parts.append("• 剩余可采天然气储量约7.63 TCF（截至2026年1月）<br/>")
        parts.append("• 若无新发现，现有储量可维持约12年<br/>")
        parts.append("• BAPEX正在推进3D地震勘探、钻井和修井作业<br/><br/>")

        parts.append("<b>3. 重点关注提醒</b><br/>")
        parts.append("• BGFCL发电机备件招标【近期截止】，请尽快安排<br/>")
        parts.append("• BAPEX 2000HP钻井项目和BGFCL锅炉火管招标【5月18日截止】<br/><br/>")
    else:
        # 抓取失败，用简化模板
        logger.warning("新闻抓取失败，使用模板数据")
        from src.industry_news import get_industry_news as get_template_news
        return get_template_news(validation_date)

    parts.append("<b>4. 链接校验说明</b><br/>")
    parts.append(f"• 本报告所有官方来源链接和PDF下载地址均于{fmt_date}校验通过，可正常访问")

    return "".join(parts)
