# -*- coding: utf-8 -*-
"""应用配置模块 —— 孟加拉石油公司国际招标标讯报告 v3.2"""

import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple


@dataclass
class AppConfig:
    """应用配置类。"""

    output_dir: str = field(
        default_factory=lambda: os.environ.get("TENDER_OUTPUT_DIR", "reports/")
    )
    email_smtp_server: str = field(
        default_factory=lambda: os.environ.get("EMAIL_SMTP_SERVER", "")
    )
    email_smtp_port: int = field(
        default_factory=lambda: int(os.environ.get("EMAIL_SMTP_PORT", "587"))
    )
    email_sender: str = field(
        default_factory=lambda: os.environ.get("EMAIL_SENDER", "")
    )
    email_password: str = field(
        default_factory=lambda: os.environ.get("EMAIL_PASSWORD", "")
    )
    email_recipient: str = field(
        default_factory=lambda: os.environ.get("EMAIL_RECIPIENT", "")
    )

    # 字体大小配置
    font_size: Dict[str, int] = field(
        default_factory=lambda: {
            "title": 18,
            "subtitle": 12,
            "section": 14,
            "field_name": 12,
            "key": 11,
            "special": 11,
            "summary": 12,
            "table_label": 11,
            "table_value": 11,
            "footer": 10,
        }
    )

    def validate_email_config(self) -> Tuple[bool, Optional[str]]:
        """验证邮件配置是否完整。

        Returns:
            (是否完整, 错误信息)
        """
        required_fields = [
            ("SMTP服务器", self.email_smtp_server),
            ("发件人邮箱", self.email_sender),
            ("发件人密码", self.email_password),
            ("收件人邮箱", self.email_recipient),
        ]
        missing = [name for name, value in required_fields if not value]
        if missing:
            return False, f"邮件配置不完整: {', '.join(missing)}未设置"
        if not isinstance(self.email_smtp_port, int) or self.email_smtp_port <= 0:
            return False, "SMTP端口必须是正整数"
        return True, None

    def get(self, key: str, default: Any = None) -> Any:
        """兼容旧版字典访问方式。

        Args:
            key: 配置键名
            default: 默认值

        Returns:
            配置值或默认值
        """
        mapping = {
            "output_dir": self.output_dir,
            "email_smtp_server": self.email_smtp_server,
            "email_smtp_port": self.email_smtp_port,
            "email_sender": self.email_sender,
            "email_password": self.email_password,
            "email_recipient": self.email_recipient,
            "font_size": self.font_size,
        }
        return mapping.get(key, default)

    def to_legacy_dict(self) -> Dict[str, Any]:
        """转换为旧版字典格式。"""
        return {
            "output_dir": self.output_dir,
            "email_smtp_server": self.email_smtp_server,
            "email_smtp_port": self.email_smtp_port,
            "email_sender": self.email_sender,
            "email_password": self.email_password,
            "email_recipient": self.email_recipient,
            "font_size": self.font_size,
        }


# 全局配置实例
CONFIG = AppConfig()
