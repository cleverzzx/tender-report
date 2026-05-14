# -*- coding: utf-8 -*-
"""工具函数模块 —— 字体注册、日志设置等通用功能"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# 中文字体搜索路径（按优先级排序）
FONT_PATHS = [
    # macOS
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    # Linux
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
]


def register_chinese_fonts() -> str:
    """注册中文字体，失败时返回 Helvetica。

    会按优先级尝试加载系统中的中文字体，成功注册后返回字体名称。
    如果所有字体都加载失败，则返回 'Helvetica' 作为回退。

    Returns:
        注册成功的字体名称，或 'Helvetica' 作为回退。
    """
    for path in FONT_PATHS:
        if os.path.exists(path):
            try:
                # 对于 .ttc 字体集合，指定子字体索引为 0
                if path.endswith(".ttc"):
                    pdfmetrics.registerFont(TTFont("ChineseFont", path, subfontIndex=0))
                else:
                    pdfmetrics.registerFont(TTFont("ChineseFont", path))
                print(f"      ✓ 使用字体: {path}")
                return "ChineseFont"
            except Exception as e:
                print(f"      ! 字体加载失败 {path}: {e}")
                continue

    print("      ✗ 未找到中文字体！PDF 中文可能显示为乱码。")
    print("        macOS: 请确认 PingFang.ttc 存在")
    print("        Linux: apt install fonts-wqy-microhei")
    return "Helvetica"


def setup_logging(log_dir: Optional[str] = "logs", log_level: int = logging.INFO) -> Path:
    """设置日志记录。

    Args:
        log_dir: 日志目录路径，默认为 "logs/"
        log_level: 日志级别，默认为 INFO

    Returns:
        日志文件路径
    """
    log_path = Path(log_dir) if log_dir else Path("logs")
    log_path.mkdir(parents=True, exist_ok=True)

    log_file = log_path / f"tender_report_{datetime.now().strftime('%Y%m%d')}.log"

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

    return log_file


def ensure_directory(path: str) -> Path:
    """确保目录存在，不存在则创建。

    Args:
        path: 目录路径

    Returns:
        Path 对象
    """
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def safe_getenv(key: str, default: str = "") -> str:
    """安全获取环境变量，返回字符串类型。

    Args:
        key: 环境变量名
        default: 默认值

    Returns:
        环境变量值或默认值
    """
    return os.environ.get(key, default)


def safe_getenv_int(key: str, default: int = 0) -> int:
    """安全获取环境变量并转为整数。

    Args:
        key: 环境变量名
        default: 默认值

    Returns:
        整数类型的环境变量值或默认值
    """
    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def truncate_string(s: str, max_length: int, suffix: str = "...") -> str:
    """截断字符串到指定长度。

    Args:
        s: 原始字符串
        max_length: 最大长度
        suffix: 截断后缀

    Returns:
        截断后的字符串
    """
    if len(s) <= max_length:
        return s
    return s[: max_length - len(suffix)] + suffix


def clean_html(text: str) -> str:
    """清理 HTML 标签，用于非 HTML 上下文的文本显示。

    Args:
        text: 可能包含 HTML 的文本

    Returns:
        清理后的纯文本
    """
    import re

    # 移除 HTML 标签
    text = re.sub(r"<[^>]+>", "", text)
    # 解码 HTML 实体
    text = text.replace("&nbsp;", " ")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&amp;", "&")
    text = text.replace("&quot;", '"')
    return text


def format_datetime(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """格式化日期时间为字符串。

    Args:
        dt: datetime 对象
        fmt: 格式字符串

    Returns:
        格式化后的字符串
    """
    return dt.strftime(fmt)
