# -*- coding: utf-8 -*-
"""
孟加拉石油公司国际招标标讯报告生成工具
版本: v3.1 (2026-05-14)
功能: 自动爬取Petrobangla/BAPEX/SGFL/BGFCL官方网站标讯，生成标准格式PDF报告
"""

import logging
from datetime import datetime
from pathlib import Path

from config import CONFIG, OFFICIAL_URLS
from src.cli import parse_args
from src.data_manager import get_tender_data
from src.email_sender import EmailSender
from src.pdf_generator import PDFGenerator
from src.scraper import print_validation_report, validate_all_links
from src.utils import register_chinese_fonts, setup_logging

logger = logging.getLogger(__name__)


def main() -> int:
    """主函数。

    Returns:
        退出码 (0 表示成功)
    """
    # 解析命令行参数
    args = parse_args()

    # 设置日志
    log_level = logging.DEBUG if args.verbose else logging.INFO
    log_file = setup_logging(log_level=log_level)
    logger.info("=== 标讯报告生成开始 ===")

    print("=" * 70)
    print("  孟加拉石油公司国际招标标讯报告生成工具 v3.1")
    print("=" * 70)

    # 注册字体
    chinese_font = register_chinese_fonts()

    # 链接校验
    if args.validate or args.validate_only:
        print(f"\n[校验] 正在校验 {len(OFFICIAL_URLS)} 个标讯的所有链接...")
        results = validate_all_links()
        print_validation_report(results)

    if args.validate_only:
        print("\n链接校验完成，未生成报告。")
        logger.info("=== 仅链接校验完成 ===")
        return 0

    # 获取数据
    print("\n[1/2] 正在获取标讯数据...")
    tenders, new_count, stats = get_tender_data(try_scrape=args.scrape)
    total = sum(len(v) for v in tenders.values())
    print(f"      ✓ 共 {total} 条标讯")
    for company in ["BAPEX", "BGFCL", "SGFL"]:
        count = len(tenders.get(company, []))
        print(f"        {company}: {count} 条")

    # 生成 PDF
    print(f"\n[2/2] 正在生成PDF报告...")
    generator = PDFGenerator(chinese_font=chinese_font)
    output_path = generator.generate(
        tenders=tenders,
        output_filename=args.output,
        output_dir=args.output_dir,
    )
    print(f"      ✓ PDF已生成: {output_path}")

    # 邮件推送
    if not args.no_email:
        print(f"\n[邮件] 正在发送邮件...")
        email_sender = EmailSender()
        success, error = email_sender.send_pdf_report(output_path)
        if not success and error:
            logger.warning(f"邮件发送失败: {error}")

    # 完成
    print("\n" + "=" * 70)
    print(f"  输出文件: {output_path}")
    print(f"  生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  日志文件: {log_file}")
    print("=" * 70)

    logger.info("=== 标讯报告生成完成 ===")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
