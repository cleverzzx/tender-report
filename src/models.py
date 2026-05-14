# -*- coding: utf-8 -*-
"""数据模型模块 —— 标讯追踪工具类型定义"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class TenderField:
    """单个标讯字段（键值对）"""

    name: str
    value: str

    def to_list(self) -> List[str]:
        """转换为列表格式用于旧版兼容"""
        return [self.name, self.value]


@dataclass
class Tender:
    """标讯数据模型"""

    title: str
    key: str
    special: str
    fields: List[TenderField]
    _source: str = "fallback"  # fallback, scraped, merged
    _url: Optional[str] = None
    _is_new: bool = False
    _hash: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式用于旧版兼容"""
        return {
            "title": self.title,
            "key": self.key,
            "special": self.special,
            "fields": [f.to_list() for f in self.fields],
            "_source": self._source,
            "_url": self._url,
            "_is_new": self._is_new,
            "_hash": self._hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Tender":
        """从字典创建 Tender 对象"""
        fields_data = data.get("fields", [])
        fields = [
            TenderField(name=f[0], value=f[1]) if isinstance(f, (list, tuple)) else TenderField(name=f.get("name", ""), value=f.get("value", ""))
            for f in fields_data
        ]
        return cls(
            title=data.get("title", ""),
            key=data.get("key", ""),
            special=data.get("special", ""),
            fields=fields,
            _source=data.get("_source", "fallback"),
            _url=data.get("_url"),
            _is_new=data.get("_is_new", False),
            _hash=data.get("_hash"),
        )

    def get_field_value(self, field_name: str) -> Optional[str]:
        """获取指定字段的值"""
        for f in self.fields:
            if f.name == field_name:
                return f.value
        return None

    def get_publish_date(self) -> Optional[datetime]:
        """从字段中提取发布日期"""
        date_fields = ["发布日期", "Publish Date", "Published Date"]
        for field_name in date_fields:
            value = self.get_field_value(field_name)
            if value:
                # 尝试解析日期
                date_str = value.split("/")[0].strip().split()[0]
                try:
                    return datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    continue
        return None


@dataclass
class ScrapedEntry:
    """爬取到的原始条目"""

    title: str
    url: str
    date_text: str = ""
    company: Optional[str] = None

    def normalize(self) -> Tender:
        """转换为标准化 Tender 对象"""
        # 从标题推断公司
        title_lower = self.title.lower()
        inferred_company = self.company
        if not inferred_company:
            if "bapex" in title_lower:
                inferred_company = "BAPEX"
            elif "bgfcl" in title_lower:
                inferred_company = "BGFCL"
            elif "sgfl" in title_lower:
                inferred_company = "SGFL"

        fields = [
            TenderField("招标编号", "未知（请查看详情页）"),
            TenderField("发布日期", self.date_text or "详见详情页"),
            TenderField("采购内容", self.title),
            TenderField(
                "官方来源",
                f"<a href='{self.url}' color='blue'>点击查看详情页</a>" if self.url else "未提供",
            ),
        ]

        return Tender(
            title=self.title,
            key=f"状态: <b>新爬取</b> | 来源: {inferred_company or 'Unknown'}",
            special="<b>从官网爬取</b> | 请访问详情页获取完整信息",
            fields=fields,
            _source="scraped",
            _url=self.url,
        )


@dataclass
class ValidationResult:
    """链接校验结果"""

    url: str
    ok: bool
    status_code: Optional[int] = None
    error: Optional[str] = None

    @property
    def status_icon(self) -> str:
        """返回状态图标"""
        return "✓" if self.ok else "✗"


@dataclass
class PDFConfig:
    """PDF 生成配置"""

    output_dir: str = "reports/"
    font_size_title: int = 18
    font_size_subtitle: int = 12
    font_size_section: int = 14
    font_size_field: int = 12
    font_size_key: int = 11
    font_size_special: int = 11
    font_size_summary: int = 12
    font_size_table_label: int = 11
    font_size_table_value: int = 11
    font_size_footer: int = 10

    def to_font_sizes(self) -> Dict[str, int]:
        """转换为旧版 font_size 字典"""
        return {
            "title": self.font_size_title,
            "subtitle": self.font_size_subtitle,
            "section": self.font_size_section,
            "field_name": self.font_size_field,
            "key": self.font_size_key,
            "special": self.font_size_special,
            "summary": self.font_size_summary,
            "table_label": self.font_size_table_label,
            "table_value": self.font_size_table_value,
            "footer": self.font_size_footer,
        }


@dataclass
class EmailConfig:
    """邮件配置"""

    smtp_server: str = ""
    smtp_port: int = 587
    sender: str = ""
    password: str = ""
    recipient: str = ""

    def is_configured(self) -> bool:
        """检查邮件配置是否完整"""
        return all([self.smtp_server, self.sender, self.password, self.recipient])


@dataclass
class HistoryEntry:
    """历史记录条目"""

    title: str
    company: str
    first_seen: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "company": self.company,
            "first_seen": self.first_seen.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HistoryEntry":
        first_seen_str = data.get("first_seen", "")
        try:
            first_seen = datetime.fromisoformat(first_seen_str)
        except (ValueError, TypeError):
            first_seen = datetime.now()
        return cls(
            title=data.get("title", ""),
            company=data.get("company", ""),
            first_seen=first_seen,
        )


@dataclass
class TendersByCompany:
    """按公司分类的标讯集合"""

    bapex: List[Tender] = field(default_factory=list)
    bgfcl: List[Tender] = field(default_factory=list)
    sgfl: List[Tender] = field(default_factory=list)

    def get(self, company: str) -> List[Tender]:
        """获取指定公司的标讯列表"""
        company_map = {
            "BAPEX": self.bapex,
            "BGFCL": self.bgfcl,
            "SGFL": self.sgfl,
        }
        return company_map.get(company, [])

    def set(self, company: str, tenders: List[Tender]) -> None:
        """设置指定公司的标讯列表"""
        if company == "BAPEX":
            self.bapex = tenders
        elif company == "BGFCL":
            self.bgfcl = tenders
        elif company == "SGFL":
            self.sgfl = tenders

    def all_tenders(self) -> List[Tender]:
        """获取所有标讯"""
        return self.bapex + self.bgfcl + self.sgfl

    def total_count(self) -> int:
        """获取标讯总数"""
        return len(self.bapex) + len(self.bgfcl) + len(self.sgfl)

    def to_dict(self) -> Dict[str, List[Tender]]:
        """转换为字典格式"""
        return {
            "BAPEX": self.bapex,
            "BGFCL": self.bgfcl,
            "SGFL": self.sgfl,
        }


@dataclass
class DetectionStats:
    """新标讯检测统计"""

    total: int = 0
    new: int = 0
    by_company: Dict[str, Dict[str, int]] = field(default_factory=dict)
