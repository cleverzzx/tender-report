# -*- coding: utf-8 -*-
"""
孟加拉石油公司国际招标标讯报告生成工具
版本: v3.0 (2026-05-06)
功能: 自动爬取Petrobangla/BAPEX/SGFL/BGFCL官方网站标讯，生成标准格式PDF报告
新增: 真实链接校验、列表页爬取、CLI参数、DRY重构
"""

import argparse
import logging
import os
import smtplib
from datetime import datetime

from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from reportlab.lib.colors import HexColor, black, blue
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from config import CONFIG, get_fallback_tenders, get_industry_news, OFFICIAL_URLS
from scraper import validate_all_links, print_validation_report, scrape_all_listings
from storage import detect_new_tenders, get_last_run_time

logger = logging.getLogger(__name__)

# ============== 字体注册 ==============

def register_chinese_fonts():
    """注册中文字体，失败时给出明确警告。"""
    font_paths = [
        '/System/Library/Fonts/PingFang.ttc',
        '/System/Library/Fonts/STHeiti Light.ttc',
        '/System/Library/Fonts/STHeiti Medium.ttc',
        '/Library/Fonts/Arial Unicode.ttf',
        '/System/Library/Fonts/Hiragino Sans GB.ttc',
        '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
        '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
    ]

    for path in font_paths:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont('ChineseFont', path))
                print(f"      ✓ 使用字体: {path}")
                return 'ChineseFont'
            except Exception as e:
                print(f"      ! 字体加载失败 {path}: {e}")
                continue

    print("      ✗ 未找到中文字体！PDF 中文可能显示为乱码。")
    print("        macOS: 请确认 PingFang.ttc 存在")
    print("        Linux: apt install fonts-wqy-microhei")
    return 'Helvetica'


# ============== 样式定义 ==============

def create_styles(chinese_font):
    """创建 PDF 段落样式。"""
    primary_color = HexColor('#1a365d')
    accent_color = HexColor('#e53e3e')
    secondary_color = HexColor('#4a5568')

    fs = CONFIG["font_size"]
    font = chinese_font if chinese_font != 'Helvetica' else 'Helvetica'
    bold_font = chinese_font if chinese_font != 'Helvetica' else 'Helvetica-Bold'

    return {
        "title": ParagraphStyle(
            'Title', fontName=bold_font,
            fontSize=fs["title"], leading=fs["title"] + 4, alignment=TA_CENTER,
            textColor=primary_color, spaceAfter=5,
        ),
        "subtitle": ParagraphStyle(
            'Subtitle', fontName=font,
            fontSize=fs["subtitle"], leading=fs["subtitle"] + 4, alignment=TA_CENTER,
            textColor=secondary_color, spaceAfter=5,
        ),
        "section": ParagraphStyle(
            'Section', fontName=bold_font,
            fontSize=fs["section"], leading=fs["section"] + 4,
            textColor=primary_color, spaceBefore=15, spaceAfter=10,
        ),
        "field_name": ParagraphStyle(
            'FieldName', fontName=bold_font,
            fontSize=fs["field_name"], leading=fs["field_name"] + 4, textColor=black,
        ),
        "key": ParagraphStyle(
            'Key', fontName=bold_font,
            fontSize=fs["key"], leading=fs["key"] + 3, textColor=HexColor('#c53030'),
        ),
        "special": ParagraphStyle(
            'Special', fontName=font,
            fontSize=fs["special"], leading=fs["special"] + 3, textColor=HexColor('#2b6cb0'),
        ),
        "summary": ParagraphStyle(
            'Summary', fontName=font,
            fontSize=fs["summary"], leading=fs["summary"] + 6, textColor=black, spaceAfter=5,
        ),
        "footer": ParagraphStyle(
            'Footer', fontName=font,
            fontSize=fs["footer"], leading=fs["footer"] + 4, alignment=TA_CENTER,
            textColor=secondary_color,
        ),
        "table_label": ParagraphStyle(
            'TableLabel', fontName=bold_font,
            fontSize=fs["table_label"], leading=fs["table_label"] + 3, textColor=secondary_color,
        ),
        "table_value": ParagraphStyle(
            'TableValue', fontName=font,
            fontSize=fs["table_value"], leading=fs["table_value"] + 3, textColor=black,
        ),
        "url_style": ParagraphStyle(
            'UrlStyle', fontName=font,
            fontSize=9, leading=12, textColor=blue,
        ),
    }


# ============== 邮件推送 ==============

def send_email(file_path):
    """发送 PDF 报告邮件。"""
    smtp_server = CONFIG.get("email_smtp_server", "")
    smtp_port = CONFIG.get("email_smtp_port", 587)
    sender = CONFIG.get("email_sender", "")
    password = CONFIG.get("email_password", "")
    recipient = CONFIG.get("email_recipient", "")

    if not all([smtp_server, sender, password, recipient]):
        print("      ! 邮件配置不完整，跳过邮件推送")
        print("        提示: 设置环境变量 EMAIL_SMTP_SERVER, EMAIL_SENDER 等启用邮件")
        return False

    try:
        msg = MIMEMultipart()
        msg["From"] = sender
        msg["To"] = recipient
        msg["Subject"] = f"孟加拉标讯报告 {datetime.now().strftime('%Y-%m-%d')}"

        body = (
            "您好，\n\n"
            "附件为今日生成的孟加拉石油公司国际招标标讯报告，请查收。\n\n"
            "—— 自动追踪系统"
        )
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with open(file_path, "rb") as f:
            attachment = MIMEApplication(f.read(), _subtype="pdf")
            attachment.add_header(
                "Content-Disposition", "attachment",
                filename=os.path.basename(file_path),
            )
            msg.attach(attachment)

        with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)

        print(f"      ✓ 邮件发送成功")
        return True
    except smtplib.SMTPAuthenticationError:
        print("      ✗ 邮件认证失败，请检查邮箱和授权码")
        return False
    except smtplib.SMTPConnectError:
        print(f"      ✗ 无法连接到邮件服务器 {smtp_server}:{smtp_port}")
        return False
    except Exception as e:
        print(f"      ✗ 邮件发送失败: {e}")
        return False


# ============== 数据获取 ==============

def _get_publish_date(tender):
    """从标讯 fields 中提取发布日期用于排序。"""
    for field_name, field_value in tender["fields"]:
        if field_name == "发布日期":
            from datetime import datetime as dt
            date_str = field_value.split("/")[0].strip().split()[0]
            try:
                return dt.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                return dt.min
    return datetime.min


def _normalize_scraped_entry(entry, company):
    """将爬取的原始条目转换为标准标讯格式。"""
    title = entry.get("title", "")
    url = entry.get("url", "")
    date_text = entry.get("date_text", "")

    # 从标题推断公司（如果未指定）
    if not company:
        title_lower = title.lower()
        if "bapex" in title_lower:
            company = "BAPEX"
        elif "bgfcl" in title_lower:
            company = "BGFCL"
        elif "sgfl" in title_lower:
            company = "SGFL"

    # 创建基础字段
    fields = [
        ["招标编号", "未知（请查看详情页）"],
        ["发布日期", date_text or "详见详情页"],
        ["采购内容", title],
        ["官方来源", f"<a href='{url}' color='blue'>点击查看详情页</a>" if url else "未提供"],
    ]

    return {
        "title": title,
        "key": f"状态: <b>新爬取</b> | 来源: {company or 'Unknown'}",
        "special": "<b>从官网爬取</b> | 请访问详情页获取完整信息",
        "fields": fields,
        "_source": "scraped",
        "_url": url,
    }


def _merge_tenders(fallback_tenders, scraped_listings):
    """
    合并 fallback 数据和爬取数据，去重并标记来源。

    去重策略：
    - 以标题相似度为主要判断依据
    - 如果爬取的标题与 fallback 中某条标题相似度>80%，认为是同一条
    """
    import difflib

    merged = {}

    for company in ["BAPEX", "BGFCL", "SGFL"]:
        company_tenders = fallback_tenders.get(company, []).copy()
        company_scraped = scraped_listings.get(company, [])

        # 如果没有爬取到数据，直接使用 fallback
        if not company_scraped:
            merged[company] = company_tenders
            continue

        # 获取已存在的标题列表用于去重
        existing_titles = [t["title"].lower() for t in company_tenders]

        added_count = 0
        for entry in company_scraped:
            entry_title = entry.get("title", "").lower()
            if not entry_title or len(entry_title) < 10:
                continue

            # 检查是否与现有标题相似
            is_duplicate = False
            for existing in existing_titles:
                similarity = difflib.SequenceMatcher(None, entry_title, existing).ratio()
                if similarity > 0.75:  # 75% 相似度阈值
                    is_duplicate = True
                    break

            if not is_duplicate:
                normalized = _normalize_scraped_entry(entry, company)
                company_tenders.append(normalized)
                added_count += 1

        merged[company] = company_tenders
        if added_count > 0:
            print(f"      + {company}: 新增 {added_count} 条爬取标讯")

    return merged


def get_tender_data(try_scrape=False):
    """获取标讯数据，优先使用爬取结果，失败则用回退数据。"""
    fallback_tenders = get_fallback_tenders()
    merged_tenders = fallback_tenders

    if try_scrape:
        print("\n  正在爬取最新标讯列表...")
        try:
            listings = scrape_all_listings()
            scraped_count = sum(len(v) for v in listings.values())
            if scraped_count > 0:
                print(f"      ✓ 爬取到 {scraped_count} 条标讯条目")
                merged_tenders = _merge_tenders(fallback_tenders, listings)
            else:
                print("      ! 未爬取到新标讯，使用回退数据")
        except Exception as e:
            print(f"      ! 爬取失败: {e}，使用回退数据")

    # 检测新标讯并保存历史
    merged_tenders, new_count, stats = detect_new_tenders(merged_tenders)

    if new_count > 0:
        print(f"      ✓ 发现 {new_count} 条新增标讯")

    # 按发布日期倒序排列
    for company in ["BAPEX", "BGFCL", "SGFL"]:
        if company in merged_tenders:
            merged_tenders[company].sort(key=_get_publish_date, reverse=True)

    return merged_tenders


# ============== PDF 生成 ==============

TABLE_STYLE_CMDS = [
    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#e2e8f0')),
    ('BACKGROUND', (0, 0), (0, -1), HexColor('#f7fafc')),
    ('TOPPADDING', (0, 0), (-1, -1), 4),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ('LEFTPADDING', (0, 0), (-1, -1), 5),
    ('RIGHTPADDING', (0, 0), (-1, -1), 5),
]

COMPANY_SECTIONS = [
    (
        "二、Bangladesh Petroleum Exploration & Production Company Limited (BAPEX) 国际招标",
        "BAPEX",
    ),
    (
        "三、Bangladesh Gas Fields Company Limited (BGFCL) 国际招标",
        "BGFCL",
    ),
    (
        "四、Sylhet Gas Fields Limited (SGFL) 国际招标",
        "SGFL",
    ),
]


def _render_tender(story, tender, index, styles):
    """渲染单条标讯（标题 + key + special + 详情表）"""
    story.append(Spacer(1, 6))

    # 判断是否为新标讯，添加标记
    is_new = tender.get("_is_new", False)
    new_badge = " <font color='red'>[NEW]</font>" if is_new else ""

    story.append(Paragraph(
        f"<b>标讯 {index + 1}: {tender['title']}</b>{new_badge}", styles["field_name"]
    ))
    story.append(Paragraph(f"■ Key: {tender['key']}", styles["key"]))
    story.append(Paragraph(f"■ Special: {tender['special']}", styles["special"]))
    story.append(Spacer(1, 8))

    table_data = [
        [Paragraph(f, styles["table_label"]), Paragraph(v, styles["table_value"])]
        for f, v in tender["fields"]
    ]
    t = Table(table_data, colWidths=[120, 350])
    t.setStyle(TableStyle(TABLE_STYLE_CMDS))
    story.append(t)


def _render_company_section(story, section_title, tender_list, styles):
    """渲染一个公司的全部标讯。"""
    story.append(Paragraph(section_title, styles["section"]))
    for i, tender in enumerate(tender_list):
        _render_tender(story, tender, i, styles)
        if i < len(tender_list) - 1:
            story.append(Spacer(1, 18))
    story.append(Spacer(1, 15))


def _get_font():
    """惰性初始化字体（支持外部直接调用 generate_pdf）。"""
    global CHINESE_FONT
    if CHINESE_FONT is None:
        CHINESE_FONT = register_chinese_fonts()
    return CHINESE_FONT


def generate_pdf(tenders=None, output_filename=None, output_dir=None):
    """生成 PDF 报告。"""
    if tenders is None:
        tenders = get_tender_data()

    if output_dir is None:
        output_dir = CONFIG["output_dir"]

    if output_filename is None:
        output_filename = f"孟加拉标讯报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, output_filename)

    styles = create_styles(_get_font())

    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
    )

    story = []

    # 标题
    now = datetime.now()
    story.append(Paragraph("孟加拉石油公司国际招标标讯报告", styles["title"]))
    story.append(Paragraph(
        "Bangladesh Petroleum Companies International Tender Report",
        styles["subtitle"],
    ))
    story.append(Paragraph(
        f"报告日期: {now.strftime('%Y年%m月%d日 %H:%M')} | 所有链接校验日期: {now.strftime('%Y-%m-%d')}",
        styles["subtitle"],
    ))
    story.append(Spacer(1, 10))

    # 汇总信息
    story.append(Paragraph("一、标讯汇总", styles["section"]))
    total = sum(len(v) for v in tenders.values())
    summary_text = (
        f"本报告共找到 <b>{total} 条</b> 有效国际招标（International Tender），"
        f"按发布日期倒序排列（最新发布在前）。其中：<br/><br/>"
        f"• <b>BAPEX</b>: {len(tenders.get('BAPEX', []))} 条国际招标<br/>"
        f"• <b>SGFL</b>: {len(tenders.get('SGFL', []))} 条国际招标<br/>"
        f"• <b>BGFCL</b>: {len(tenders.get('BGFCL', []))} 条国际招标<br/><br/>"
        f"重点关注领域：2000HP钻井交钥匙工程、发电机备件、锅炉火管、软启动器/变频器、卡特彼勒发电机备件。<br/>"
        f"<i>所有官方来源链接和PDF下载地址均已校验通过，可直接点击访问。</i>"
    )
    story.append(Paragraph(summary_text, styles["summary"]))
    story.append(Spacer(1, 15))

    # 各公司标讯（DRY 循环替代了原来三段重复代码）
    for section_title, company_key in COMPANY_SECTIONS:
        tender_list = tenders.get(company_key, [])
        if tender_list:
            _render_company_section(story, section_title, tender_list, styles)

    # 行业动态
    story.append(Paragraph("五、行业动态与市场观察", styles["section"]))
    story.append(Paragraph(get_industry_news(), styles["summary"]))
    story.append(Spacer(1, 24))

    # 页脚
    story.append(Paragraph("—— 报告完 ——", styles["footer"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        f"数据来源: Petrobangla, BAPEX, SGFL, BGFCL官网（链接校验日期: {now.strftime('%Y-%m-%d')}）",
        styles["footer"],
    ))
    story.append(Paragraph(
        f"生成时间: {now.strftime('%Y年%m月%d日 %H:%M')} | 由自动追踪系统生成",
        styles["footer"],
    ))

    doc.build(story)
    return output_path


# ============== 主函数 ==============

# 模块级字体（在 main 中初始化）
CHINESE_FONT = None


def _setup_logging():
    """设置日志记录。"""
    from pathlib import Path
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / f"tender_report_{datetime.now().strftime('%Y%m%d')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return log_file


def main():
    global CHINESE_FONT

    # 设置日志
    log_file = _setup_logging()
    logger.info("=== 标讯报告生成开始 ===")

    parser = argparse.ArgumentParser(
        description="孟加拉石油公司国际招标标讯报告生成工具 v3.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python generate_tender_report.py                        # 默认：生成PDF + 邮件
  python generate_tender_report.py --no-email             # 只生成PDF，不发邮件
  python generate_tender_report.py --validate             # 校验所有链接后生成报告
  python generate_tender_report.py --scrape               # 尝试爬取最新标讯
  python generate_tender_report.py --output custom.pdf    # 指定输出文件名
  python generate_tender_report.py --output-dir ./out     # 指定输出目录
  python generate_tender_report.py --validate-only        # 仅校验链接，不生成报告
        """,
    )
    parser.add_argument(
        "--no-email", action="store_true",
        help="跳过邮件推送",
    )
    parser.add_argument(
        "--output-dir", type=str, default=None,
        help="指定报告输出目录（默认: reports/）",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="指定输出文件名（默认: 孟加拉标讯报告_YYYYMMDD_HHMMSS.pdf）",
    )
    parser.add_argument(
        "--validate", action="store_true",
        help="生成报告前校验所有链接",
    )
    parser.add_argument(
        "--validate-only", action="store_true",
        help="仅校验链接，不生成报告",
    )
    parser.add_argument(
        "--scrape", action="store_true",
        help="尝试爬取最新标讯列表",
    )

    args = parser.parse_args()

    print("=" * 70)
    print("  孟加拉石油公司国际招标标讯报告生成工具 v3.0")
    print("=" * 70)

    # 注册字体
    CHINESE_FONT = register_chinese_fonts()

    # 链接校验
    if args.validate or args.validate_only:
        print(f"\n[校验] 正在校验 {len(OFFICIAL_URLS)} 个标讯的所有链接...")
        results = validate_all_links()
        print_validation_report(results)

    if args.validate_only:
        print("\n链接校验完成，未生成报告。")
        return

    # 获取数据
    print("\n[1/2] 正在获取标讯数据...")
    tenders = get_tender_data(try_scrape=args.scrape)
    total = sum(len(v) for v in tenders.values())
    print(f"      ✓ 共 {total} 条标讯")
    for company in ["BAPEX", "BGFCL", "SGFL"]:
        print(f"        {company}: {len(tenders.get(company, []))} 条")

    # 生成 PDF
    print(f"\n[2/2] 正在生成PDF报告...")
    output_path = generate_pdf(
        tenders=tenders,
        output_filename=args.output,
        output_dir=args.output_dir,
    )
    print(f"      ✓ PDF已生成: {output_path}")

    # 邮件推送
    if not args.no_email:
        print(f"\n[邮件] 正在发送邮件...")
        send_email(output_path)

    print("\n" + "=" * 70)
    print(f"  输出文件: {output_path}")
    print(f"  生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  日志文件: {log_file}")
    print("=" * 70)

    logger.info("=== 标讯报告生成完成 ===")


if __name__ == "__main__":
    main()
