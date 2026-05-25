# -*- coding: utf-8 -*-
"""PDF 生成模块 —— 标讯报告生成器 v3.1"""

import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from reportlab.lib.colors import HexColor, black, blue
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (  # type: ignore[attr-defined]
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from config import CONFIG
from src.models import Tender
from src.utils import register_chinese_fonts

logger = logging.getLogger(__name__)


class PDFGenerator:
    """PDF 报告生成器"""

    # 表格样式命令
    TABLE_STYLE_CMDS: List[Tuple] = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#e2e8f0")),
        ("BACKGROUND", (0, 0), (0, -1), HexColor("#f7fafc")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]

    # 公司章节配置（编号前缀在渲染时动态添加）
    COMPANY_SECTIONS: List[Tuple[str, str]] = [
        (
            "Bangladesh Petroleum Exploration & Production Company Limited (BAPEX) 国际招标",
            "BAPEX",
        ),
        (
            "Bangladesh Gas Fields Company Limited (BGFCL) 国际招标",
            "BGFCL",
        ),
        (
            "Sylhet Gas Fields Limited (SGFL) 国际招标",
            "SGFL",
        ),
        (
            "Petrobangla 国际招标",
            "Petrobangla",
        ),
    ]

    def __init__(self, chinese_font: Optional[str] = None) -> None:
        """初始化 PDF 生成器。

        Args:
            chinese_font: 中文字体名称，None 时自动注册
        """
        self.primary_color = HexColor("#1a365d")
        self.accent_color = HexColor("#e53e3e")
        self.secondary_color = HexColor("#4a5568")
        self.chinese_font = chinese_font or register_chinese_fonts()
        self.styles = self._create_styles()

    def _create_styles(self) -> Dict[str, ParagraphStyle]:
        """创建 PDF 段落样式。

        Returns:
            样式字典
        """
        fs = CONFIG.get("font_size", {})
        font = self.chinese_font if self.chinese_font != "Helvetica" else "Helvetica"
        bold_font = self.chinese_font if self.chinese_font != "Helvetica" else "Helvetica-Bold"

        return {
            "title": ParagraphStyle(
                "Title",
                fontName=bold_font,
                fontSize=fs.get("title", 18),
                leading=fs.get("title", 18) + 4,
                alignment=TA_CENTER,
                textColor=self.primary_color,
                spaceAfter=5,
            ),
            "subtitle": ParagraphStyle(
                "Subtitle",
                fontName=font,
                fontSize=fs.get("subtitle", 12),
                leading=fs.get("subtitle", 12) + 4,
                alignment=TA_CENTER,
                textColor=self.secondary_color,
                spaceAfter=5,
            ),
            "section": ParagraphStyle(
                "Section",
                fontName=bold_font,
                fontSize=fs.get("section", 14),
                leading=fs.get("section", 14) + 4,
                textColor=self.primary_color,
                spaceBefore=15,
                spaceAfter=10,
            ),
            "field_name": ParagraphStyle(
                "FieldName",
                fontName=bold_font,
                fontSize=fs.get("field_name", 12),
                leading=fs.get("field_name", 12) + 4,
                textColor=black,
            ),
            "key": ParagraphStyle(
                "Key",
                fontName=bold_font,
                fontSize=fs.get("key", 11),
                leading=fs.get("key", 11) + 3,
                textColor=HexColor("#c53030"),
            ),
            "special": ParagraphStyle(
                "Special",
                fontName=font,
                fontSize=fs.get("special", 11),
                leading=fs.get("special", 11) + 3,
                textColor=HexColor("#2b6cb0"),
            ),
            "summary": ParagraphStyle(
                "Summary",
                fontName=font,
                fontSize=fs.get("summary", 12),
                leading=fs.get("summary", 12) + 6,
                textColor=black,
                spaceAfter=5,
            ),
            "footer": ParagraphStyle(
                "Footer",
                fontName=font,
                fontSize=fs.get("footer", 10),
                leading=fs.get("footer", 10) + 4,
                alignment=TA_CENTER,
                textColor=self.secondary_color,
            ),
            "table_label": ParagraphStyle(
                "TableLabel",
                fontName=bold_font,
                fontSize=fs.get("table_label", 11),
                leading=fs.get("table_label", 11) + 3,
                textColor=self.secondary_color,
            ),
            "table_value": ParagraphStyle(
                "TableValue",
                fontName=font,
                fontSize=fs.get("table_value", 11),
                leading=fs.get("table_value", 11) + 3,
                textColor=black,
            ),
            "url_style": ParagraphStyle(
                "UrlStyle",
                fontName=font,
                fontSize=9,
                leading=12,
                textColor=blue,
            ),
        }

    def _render_tender(
        self, story: List, tender: Tender, index: int, company: str = ""
    ) -> None:
        """渲染单条标讯（标题 + 公司标签 + key + special + 详情表）"""
        story.append(Spacer(1, 6))

        is_new = tender._is_new
        new_badge = " <font color='red'>[NEW]</font>" if is_new else ""
        company_tag = f" <font color='#4a5568'>[{company}]</font>" if company else ""

        story.append(
            Paragraph(
                f"<b>标讯 {index + 1}: {tender.title}</b>{new_badge}{company_tag}",
                self.styles["field_name"],
            )
        )
        story.append(Paragraph(f"■ Key: {tender.key}", self.styles["key"]))
        story.append(Paragraph(f"■ Special: {tender.special}", self.styles["special"]))
        story.append(Spacer(1, 8))

        table_data = [
            [
                Paragraph(field.name, self.styles["table_label"]),
                Paragraph(field.value, self.styles["table_value"]),
            ]
            for field in tender.fields
        ]
        t = Table(table_data, colWidths=[120, 350])
        t.setStyle(TableStyle(self.TABLE_STYLE_CMDS))
        story.append(t)

    def _render_company_section(
        self, story: List, section_title: str, tender_list: List[Tender], start_index: int = 0
    ) -> int:
        """渲染一个公司的全部标讯。

        Args:
            story: PDF 故事板列表
            section_title: 章节标题
            tender_list: 标讯列表
            start_index: 全局起始序号

        Returns:
            渲染后的下一个全局序号
        """
        if not tender_list:
            story.append(Paragraph(section_title, self.styles["section"]))
            story.append(
                Paragraph(
                    "<i>暂无进行中的国际招标标讯</i>",
                    self.styles["summary"],
                )
            )
            story.append(Spacer(1, 15))
            return start_index

        story.append(Paragraph(section_title, self.styles["section"]))
        for i, tender in enumerate(tender_list):
            self._render_tender(story, tender, start_index + i)
            if i < len(tender_list) - 1:
                story.append(Spacer(1, 18))
        story.append(Spacer(1, 15))
        return start_index + len(tender_list)

    def _render_summary(
        self, story: List, tenders: Dict[str, List[Tender]], validation_date: datetime
    ) -> None:
        """渲染汇总信息。

        Args:
            story: PDF 故事板列表
            tenders: 标讯字典
            validation_date: 链接校验日期
        """
        story.append(Paragraph("一、标讯汇总", self.styles["section"]))

        total = sum(len(v) for v in tenders.values())

        # 只显示有标讯的公司，按章节顺序
        company_lines = []
        for _, company_key in self.COMPANY_SECTIONS:
            count = len(tenders.get(company_key, []))
            if count > 0:
                company_lines.append(f"• <b>{company_key}</b>: {count} 条国际招标")

        company_summary = "<br/>".join(company_lines) if company_lines else "暂无有效国际招标"

        summary_text = (
            f"本报告共找到 <b>{total} 条</b> 有效国际招标（International Tender），"
            f"按发布日期倒序排列（最新发布在前）。其中：<br/><br/>"
            f"{company_summary}<br/><br/>"
            f"重点关注领域：2000HP钻井交钥匙工程、发电机备件、锅炉火管、软启动器/变频器、卡特彼勒发电机备件。<br/>"
            f"<i>所有官方来源链接和PDF下载地址均已校验通过，可直接点击访问。</i>"
        )
        story.append(Paragraph(summary_text, self.styles["summary"]))
        story.append(Spacer(1, 15))

    def _render_industry_news(self, story: List, validation_date: datetime, section_num: int = 5) -> None:
        """渲染行业动态。

        Args:
            story: PDF 故事板列表
            validation_date: 校验日期
            section_num: 章节序号（默认5）
        """
        from src.news_fetcher import get_industry_news_html

        chinese_nums = {2: "二", 3: "三", 4: "四", 5: "五", 6: "六"}
        num_prefix = chinese_nums.get(section_num, str(section_num))
        story.append(Paragraph(f"{num_prefix}、行业动态与市场观察", self.styles["section"]))
        story.append(Paragraph(get_industry_news_html(validation_date), self.styles["summary"]))
        story.append(Spacer(1, 24))

    def _render_footer(self, story: List, now: datetime) -> None:
        """渲染页脚。

        Args:
            story: PDF 故事板列表
            now: 当前时间
        """
        story.append(Paragraph("—— 报告完 ——", self.styles["footer"]))
        story.append(Spacer(1, 12))
        story.append(
            Paragraph(
                f"数据来源: Petrobangla, BAPEX, SGFL, BGFCL官网（链接校验日期: {now.strftime('%Y-%m-%d')}）",
                self.styles["footer"],
            )
        )
        story.append(
            Paragraph(
                f"生成时间: {now.strftime('%Y年%m月%d日 %H:%M')} | 由自动追踪系统生成",
                self.styles["footer"],
            )
        )

    def generate(
        self,
        tenders: Dict[str, List[Tender]],
        output_filename: Optional[str] = None,
        output_dir: Optional[str] = None,
        validation_date: Optional[datetime] = None,
    ) -> str:
        """生成 PDF 报告。

        Args:
            tenders: 标讯字典 {"BAPEX": [...], ...}
            output_filename: 输出文件名（可选）
            output_dir: 输出目录（可选）
            validation_date: 链接校验日期（可选，默认当前时间）

        Returns:
            生成的 PDF 文件路径
        """
        output_dir = output_dir or CONFIG.get("output_dir", "reports/")
        os.makedirs(output_dir, exist_ok=True)

        if not output_filename:
            output_filename = f"孟加拉标讯报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        output_path = os.path.join(output_dir, output_filename)
        now = datetime.now()
        validation_date = validation_date or now

        # 创建文档
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            leftMargin=1.5 * cm,
            rightMargin=1.5 * cm,
            topMargin=1.5 * cm,
            bottomMargin=1.5 * cm,
        )

        story: List = []

        # 标题
        story.append(Paragraph("孟加拉石油公司国际招标标讯报告", self.styles["title"]))
        story.append(
            Paragraph(
                "Bangladesh Petroleum Companies International Tender Report",
                self.styles["subtitle"],
            )
        )
        date_str = now.strftime("%Y年%m月%d日 %H:%M")
        valid_str = validation_date.strftime("%Y-%m-%d")
        story.append(
            Paragraph(
                f"报告日期: {date_str} | 所有链接校验日期: {valid_str}",
                self.styles["subtitle"],
            )
        )
        story.append(Spacer(1, 10))

        # 汇总信息
        self._render_summary(story, tenders, validation_date)

        # 将所有标讯按发布日期从新到旧全局排列
        all_tenders: List[Tuple[Tender, str]] = []  # (tender, company_key)
        for _, company_key in self.COMPANY_SECTIONS:
            for t in tenders.get(company_key, []):
                all_tenders.append((t, company_key))
        all_tenders.sort(
            key=lambda x: x[0].get_publish_date() or datetime.min,
            reverse=True,
        )

        # 二、标讯详情（全局连续序号，从新到旧）
        story.append(Paragraph("二、国际招标标讯详情", self.styles["section"]))
        global_index = 0
        for tender, company in all_tenders:
            self._render_tender(story, tender, global_index, company)
            global_index += 1
            if global_index < len(all_tenders):
                story.append(Spacer(1, 18))
        story.append(Spacer(1, 15))

        # 行业动态
        self._render_industry_news(story, validation_date, section_num=3)

        # 页脚
        self._render_footer(story, now)

        # 构建 PDF
        doc.build(story)
        logger.info(f"PDF 报告已生成: {output_path}")

        return output_path


# 兼容旧版 API
def generate_pdf(
    tenders: Optional[Dict[str, List[Tender]]] = None,
    output_filename: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> str:
    """生成 PDF 报告（兼容旧版 API）。

    Args:
        tenders: 标讯字典
        output_filename: 输出文件名
        output_dir: 输出目录

    Returns:
        生成的 PDF 文件路径
    """
    from src.data_manager import get_tender_data

    if tenders is None:
        tenders_data, _, _ = get_tender_data()
        tenders = tenders_data

    generator = PDFGenerator()
    return generator.generate(tenders, output_filename, output_dir)
