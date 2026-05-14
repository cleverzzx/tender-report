# -*- coding: utf-8 -*-
"""邮件发送模块 —— PDF 报告邮件推送"""

import logging
import os
import smtplib
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional, Tuple

from config import CONFIG

logger = logging.getLogger(__name__)


class EmailSender:
    """邮件发送器"""

    def __init__(
        self,
        smtp_server: str = "",
        smtp_port: int = 587,
        sender: str = "",
        password: str = "",
        recipient: str = "",
    ) -> None:
        self.smtp_server = smtp_server or CONFIG.get("email_smtp_server", "")
        self.smtp_port = smtp_port or CONFIG.get("email_smtp_port", 587)
        self.sender = sender or CONFIG.get("email_sender", "")
        self.password = password or CONFIG.get("email_password", "")
        self.recipient = recipient or CONFIG.get("email_reCIPIENT", "")

    def is_configured(self) -> bool:
        """检查邮件配置是否完整。"""
        return all([
            self.smtp_server,
            self.sender,
            self.password,
            self.recipient,
        ])

    def get_config_error(self) -> Optional[str]:
        """获取配置错误信息。"""
        missing = []
        if not self.smtp_server:
            missing.append("SMTP服务器")
        if not self.sender:
            missing.append("发件人邮箱")
        if not self.password:
            missing.append("发件人密码")
        if not self.recipient:
            missing.append("收件人邮箱")

        if missing:
            return f"邮件配置不完整: {', '.join(missing)}未设置"
        return None

    def send_pdf_report(
        self,
        file_path: str,
        subject: Optional[str] = None,
        body: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """发送 PDF 报告邮件。

        Args:
            file_path: PDF 文件路径
            subject: 邮件主题（可选，默认自动生成）
            body: 邮件正文（可选，默认使用模板）

        Returns:
            (是否成功, 错误信息)
        """
        # 检查配置
        error = self.get_config_error()
        if error:
            logger.warning(f"{error}，跳过邮件推送")
            print(f"      ! {error}")
            print("        提示: 设置环境变量 EMAIL_SMTP_SERVER, EMAIL_SENDER 等启用邮件")
            return False, error

        # 检查文件
        if not os.path.exists(file_path):
            error = f"PDF 文件不存在: {file_path}"
            logger.error(error)
            return False, error

        # 构建邮件
        try:
            msg = MIMEMultipart()
            msg["From"] = self.sender
            msg["To"] = self.recipient
            msg["Subject"] = subject or f"孟加拉标讯报告 {datetime.now().strftime('%Y-%m-%d')}"

            email_body = body or (
                "您好，\n\n"
                "附件为今日生成的孟加拉石油公司国际招标标讯报告，请查收。\n\n"
                "—— 自动追踪系统"
            )
            msg.attach(MIMEText(email_body, "plain", "utf-8"))

            # 添加附件
            with open(file_path, "rb") as f:
                attachment = MIMEApplication(f.read(), _subtype="pdf")
                attachment.add_header(
                    "Content-Disposition", "attachment",
                    filename=os.path.basename(file_path),
                )
                msg.attach(attachment)

            # 发送邮件
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30) as server:
                server.starttls()
                server.login(self.sender, self.password)
                server.send_message(msg)

            logger.info(f"邮件发送成功: {file_path}")
            print(f"      ✓ 邮件发送成功")
            return True, None

        except smtplib.SMTPAuthenticationError:
            error = "邮件认证失败，请检查邮箱和授权码"
            logger.error(error)
            print(f"      ✗ {error}")
            return False, error

        except smtplib.SMTPConnectError:
            error = f"无法连接到邮件服务器 {self.smtp_server}:{self.smtp_port}"
            logger.error(error)
            print(f"      ✗ {error}")
            return False, error

        except Exception as e:
            error = f"邮件发送失败: {e}"
            logger.error(error)
            print(f"      ✗ {error}")
            return False, error


# 兼容旧版 API
def send_email(file_path: str) -> bool:
    """发送 PDF 报告邮件（兼容旧版 API）。

    Args:
        file_path: PDF 文件路径

    Returns:
        是否成功
    """
    sender = EmailSender()
    success, _ = sender.send_pdf_report(file_path)
    return success
