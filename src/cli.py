# -*- coding: utf-8 -*-
"""CLI 模块 —— 命令行参数解析"""

import argparse
from typing import Optional


def create_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器。

    Returns:
        ArgumentParser 对象
    """
    parser = argparse.ArgumentParser(
        description="孟加拉石油公司国际招标标讯报告生成工具 v3.1",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py                        # 默认：生成PDF + 邮件
  python main.py --no-email             # 只生成PDF，不发邮件
  python main.py --validate             # 校验所有链接后生成报告
  python main.py --scrape               # 尝试爬取最新标讯
  python main.py --output custom.pdf    # 指定输出文件名
  python main.py --output-dir ./out     # 指定输出目录
  python main.py --validate-only        # 仅校验链接，不生成报告
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
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="显示详细日志",
    )

    return parser


def parse_args(args: Optional[list] = None) -> argparse.Namespace:
    """解析命令行参数。

    Args:
        args: 参数列表（None 时使用 sys.argv）

    Returns:
        解析后的参数命名空间
    """
    parser = create_parser()
    return parser.parse_args(args)
