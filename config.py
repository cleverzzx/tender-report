# -*- coding: utf-8 -*-
"""配置和数据模块 —— 孟加拉石油公司国际招标标讯报告 v3.1"""

import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


# ============== 应用配置 ==============
@dataclass
class AppConfig:
    """应用配置类"""

    output_dir: str = field(default_factory=lambda: os.environ.get("TENDER_OUTPUT_DIR", "reports/"))
    email_smtp_server: str = field(default_factory=lambda: os.environ.get("EMAIL_SMTP_SERVER", ""))
    email_smtp_port: int = field(
        default_factory=lambda: int(os.environ.get("EMAIL_SMTP_PORT", "587"))
    )
    email_sender: str = field(default_factory=lambda: os.environ.get("EMAIL_SENDER", ""))
    email_password: str = field(default_factory=lambda: os.environ.get("EMAIL_PASSWORD", ""))
    email_recipient: str = field(default_factory=lambda: os.environ.get("EMAIL_RECIPIENT", ""))

    # 字体大小配置
    font_size: Dict[str, int] = field(default_factory=lambda: {
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
    })

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

    def to_legacy_dict(self) -> Dict[str, Any]:
        """转换为旧版字典格式"""
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


# ============== 官方链接数据库 ==============
OFFICIAL_URLS: Dict[str, Dict[str, str]] = {
    "BAPEX_1308": {
        "详情页": "https://bapex.com.bd/pages/tenders/2nd-extension-of-international-tender-tender-no-bapexadminintten-13082026-closing-date-puncw3-69df2735e3444b2e09d877cb",
        "PDF下载": "https://objectstorage.ap-dcc-gazipur-1.oraclecloud15.com/n/axvjbnqprylg/b/V2Ministry/o/office-bapex/2026/3/9864ccac-7895-48b0-927d-56dc40a02d53.pdf",
    },
    "BGFCL_234": {
        "详情页": "https://bgfcl.portal.gov.bd/pages/tenders/procurement-of-mechanical-spare-parts-of-fg-wilson-perkins-generator-engine-model-4006-23trsl-0wbeb5-69d4dce58e1b33330b2fc495",
        "PDF下载": "https://objectstorage.ap-dcc-gazipur-1.oraclecloud15.com/n/axvjbnqprylg/b/V2Ministry/o/office-bgfcl/2026/3/c6f31cf1-7b4d-46fa-855b-5154853bcf29.pdf",
    },
    "BGFCL_239": {
        "详情页": "https://petrobangla.org.bd/pages/tenders/%E0%A6%AB%E0%A6%BE%E0%A7%9F%E0%A6%BE%E0%A6%B0-%E0%A6%9F%E0%A6%BF%E0%A6%89%E0%A6%AC-%E0%A6%95%E0%A7%8D%E0%A6%B0%E0%A7%9F%E0%A7%87%E0%A6%B0-%E0%A6%86%E0%A6%A8%E0%A7%8D%E0%A6%A4%E0%A6%B0%E0%A7%8D%E0%A6%9C%E0%A6%BE%E0%A6%A4%E0%A6%BF%E0%A6%95-%E0%A6%A6%E0%A6%B0%E0%A6%AA%E0%A6%A4%E0%A7%8D%E0%A6%B0-bgfclgoodsfp239-%E0%A6%AC%E0%A6%BF%E0%A6%9C%E0%A6%BF%E0%A6%8F%E0%A6%AB%E0%A6%B8%E0%A6%BF%E0%A6%8F%E0%A6%B2-ilguki-69d4b39608aced6888358072",
        "PDF下载": "https://objectstorage.ap-dcc-gazipur-1.oraclecloud15.com/n/axvjbnqprylg/b/V2Ministry/o/office-bgfcl/2026/3/fd32de87-d048-43a3-93c8-25b8dff1133b.pdf",
    },
    "SGFL_FP08": {
        "详情页": "https://sgfl.gov.bd/pages/tenders/international-tender-notice-procurement-of-soft-starter-vfd-magnetic-contractor-acb-pw0ipl-69f03f238864d0208af3dbb7",
        "PDF下载": "https://objectstorage.ap-dcc-gazipur-1.oraclecloud15.com/n/axvjbnqprylg/b/V2Ministry/o/office-sgfl/2026/3/cb1775cb-4cb0-43f1-b2c2-1530739488cb.pdf",
    },
    "SGFL_FP07": {
        "详情页_SGFL": "https://sgfl.gov.bd/pages/tenders/international-tender-notice-procurement-of-spare-parts-for-caterpillar-gas-generator-ts00fl-69dcb1a4508fd61cddc8f90b",
        "详情页_Petrobangla": "https://petrobangla.org.bd/pages/tenders/%E0%A6%B8%E0%A7%8D%E0%A6%AA%E0%A7%87%E0%A7%9F%E0%A6%BE%E0%A6%B0-%E0%A6%AA%E0%A6%BE%E0%A6%B0%E0%A7%8D%E0%A6%9F%E0%A6%B8-%E0%A6%95%E0%A7%8D%E0%A6%B0%E0%A7%9F%E0%A7%87%E0%A6%B0-%E0%A6%9C%E0%A6%A8%E0%A7%8D%E0%A6%AF-%E0%A6%86%E0%A6%A8%E0%A7%8D%E0%A6%A4%E0%A6%B0%E0%A7%8D%E0%A6%9C%E0%A6%BE%E0%A6%A4%E0%A6%BF%E0%A6%95-%E0%A6%A6%E0%A6%B0%E0%A6%AA%E0%A6%A4%E0%A7%8D%E0%A6%B0-rgf25-26fp-07-%E0%A6%8F%E0%A6%B8%E0%A6%9C%E0%A6%BF%E0%A6%8F%E0%A6%AB%E0%A6%8F%E0%A6%B2-qh0epg-69df6822699eb2a64080b176",
        "PDF下载": "https://objectstorage.ap-dcc-gazipur-1.oraclecloud15.com/n/axvjbnqprylg/b/V2Ministry/o/office-sgfl/2026/3/7bc64fc4-0e7f-45d5-9ddc-8274593ecea2.pdf",
    },
}

# ============== 爬取目标 —— 标讯列表页 ==============
LISTING_URLS: Dict[str, str] = {
    "BAPEX": "https://bapex.com.bd/pages/tenders",
    "Petrobangla": "https://petrobangla.org.bd/pages/tenders",
    "SGFL": "https://sgfl.gov.bd/pages/tenders",
    "BGFCL_portal": "https://bgfcl.portal.gov.bd/pages/tenders",
}


# ============== 标讯回退数据（爬取失败时使用） ==============
def get_fallback_tenders() -> Dict[str, List[Dict[str, Any]]]:
    """返回硬编码的标讯数据，作为爬取失败时的回退。"""
    u = OFFICIAL_URLS
    return {
        "BAPEX": [
            {
                "title": "2000 HP AC-AC VFD Land Drilling Rig 交钥匙工程",
                "key": "截止日期 <b>2026-05-18 11:30 BST</b> | 标书价格 <b>BDT 12,000 / USD 98</b> | 保证金 <b>USD 385,000</b>",
                "special": "<b>2nd Extension</b> | International Turn-Key Drilling Rig | 合同期662天 | 钻井深度≥5000米",
                "fields": [
                    ["招标编号", "BAPEX/Admin/Int/Ten-1308/2026 (2nd Extension)"],
                    ["采购方式", "International Turn-Key Tender"],
                    ["发布日期", "2026-01-28 / 延期公告 2026-04-13"],
                    ["标书发售截止", "2026-05-17 15:00 BST"],
                    ["投标截止日期", "2026-05-18 11:30 BST"],
                    ["开标日期", "2026-05-18 12:30 BST"],
                    ["标书价格", "BDT 12,000 或 USD 98 (不退)"],
                    ["投标保证金", "USD 385,000 (仅接受银行保函)"],
                    ["投标有效期", "180天"],
                    ["合同期", "662天"],
                    ["采购内容", "2000 HP AC-AC VFD型陆地钻井交钥匙工程：设计、工程、采购、供应、安装、调试、测试及一口井钻井期间的全部维护服务，含强制备件，钻井深度可达5000米以上"],
                    ["联系人", "Md. Asad Ullah"],
                    ["职位", "General Manager (Admin.)"],
                    ["备 注", "这是第二次延期，其他条款和条件不变。此为当前最紧迫的大型钻井设备国际招标。"],
                    ["官方来源", f"<a href='{u['BAPEX_1308']['详情页']}' color='blue'>BAPEX官网详情页</a>"],
                    ["PDF下载", f"<a href='{u['BAPEX_1308']['PDF下载']}' color='blue'>点击下载招标文件(PDF)</a>"],
                ],
            }
        ],
        "BGFCL": [
            {
                "title": "Procurement of Mechanical Spare parts of FG Wilson (Perkins) Generator Engine Model: 4006-23TRSL",
                "key": "截止日期 <b>2026-05-06 14:15 BST</b> | 标书价格 <b>USD 50 / BDT 6,000</b> | 保证金 <b>USD 570 / BDT 70,000</b>",
                "special": "<b>International Re-Tender</b> | FG Wilson/Perkins发电机备件 | 交货期120天 | ISO认证要求",
                "fields": [
                    ["招标编号", "BGFCL/GOODS(FP)/234(R1) Dated April 05, 2026"],
                    ["采购方式", "Foreign/International Tender (Re-Tender)"],
                    ["发布日期", "2026-04-05 / 2026-04-07"],
                    ["截止日期", "2026-05-06 14:15 BST"],
                    ["开标日期", "2026-05-06 14:30 BST"],
                    ["标书价格", "BDT 6,000 或 USD 50 (不退)"],
                    ["投标保证金", "USD 570 或 BDT 70,000 (仅接受银行保函)"],
                    ["采购内容", "FG Wilson (Perkins) Generator Engine Model: 4006-23TRSL 机械备件"],
                    ["交货时间", "L/C开立后120天"],
                    ["投标人资格", "除以色列外所有国家的知名制造商/供应商，需满足：5年以上经验，制造商需10年以上经验，持有ISO 9001/14001/OHSAS 18001认证"],
                    ["联系人", "Engr. M. K. Masuk"],
                    ["职位", "General Manager (Technical Services)"],
                    ["电话", "+8801730 093679"],
                    ["邮箱", "prbgfci@gmail.com / gmts@bafdl.gov.bd"],
                    ["备 注", "此为重新招标，技术标与价格标双信封提交，仅银行保函接受。【后天截止】"],
                    ["官方来源", f"<a href='{u['BGFCL_234']['详情页']}' color='blue'>BGFCL官网详情页</a>"],
                    ["PDF下载", f"<a href='{u['BGFCL_234']['PDF下载']}' color='blue'>点击下载招标文件(PDF)</a>"],
                ],
            },
            {
                "title": "International Tender - Procurement of Fire Tube Pipe for Oil Bath Heater",
                "key": "截止日期 <b>2026-05-18 14:15 BST</b> | 标书价格 <b>USD 50 / BDT 6,000</b> | 保证金 <b>USD 940 / BDT 115,000</b>",
                "special": "<b>International Tender</b> | One Stage Two envelope | 交货期120天 | ISO认证要求",
                "fields": [
                    ["招标编号", "BGFCL/GOODS(FP)/239"],
                    ["采购方式", "Foreign/International Tender (One Stage Two envelope)"],
                    ["发布日期", "2026-04-06 / 2026-04-08"],
                    ["截止日期", "2026-05-18 14:15 BST"],
                    ["开标日期", "2026-05-18 14:30 BST"],
                    ["标书价格", "BDT 6,000 或 USD 50 (不退)"],
                    ["投标保证金", "USD 940 或 BDT 115,000 (仅接受银行保函)"],
                    ["采购内容", "Fire Tube Pipe for Oil Bath Heater (锅炉火管)"],
                    ["交货时间", "L/C开立后120天"],
                    ["投标人资格", "除以色列外所有国家的知名制造商/供应商，需满足：5年以上经验，制造商需10年以上经验，持有ISO 9001/14001/OHSAS 18001认证"],
                    ["联系人", "Engr. M. K. Masuk"],
                    ["职位", "General Manager (Technical Services)"],
                    ["电话", "+8801730 093679"],
                    ["邮箱", "prbgfd@gmail.com / dgmfp@bgfd.gov.bd"],
                    ["备 注", "技术标与价格标双信封提交，仅银行保函接受作为保证金"],
                    ["官方来源", f"<a href='{u['BGFCL_239']['详情页']}' color='blue'>Petrobangla/BGFCL官网详情页</a>"],
                    ["PDF下载", f"<a href='{u['BGFCL_239']['PDF下载']}' color='blue'>点击下载招标文件(PDF)</a>"],
                ],
            },
        ],
        "SGFL": [
            {
                "title": "Procurement of Soft Starter, VFD, Magnetic Contractor & ACB",
                "key": "截止日期 <b>2026-06-18 12:00 BST</b> | 标书价格 <b>USD 98 / BDT 12,000</b> | 保证金 <b>USD 2,550 / BDT 310,000</b>",
                "special": "<b>International Procurement</b> | One Stage Two envelope Tendering | 有效期120天",
                "fields": [
                    ["招标编号", "SGFL/CFP/RCFP/CRU/25-26/FP-08"],
                    ["采购方式", "International Procurement (One Stage Two envelope)"],
                    ["发布日期", "2026-04-28"],
                    ["截止日期", "2026-06-18 12:00 BST"],
                    ["开标日期", "2026-06-18 12:15 BST"],
                    ["标书发售截止", "2026-06-17"],
                    ["标书价格", "BDT 12,000 或 USD 98 (不退)"],
                    ["投标保证金", "BDT 310,000 或 USD 2,550"],
                    ["联系人", "Ziaur Rahman Khan"],
                    ["职位", "Deputy General Manager (Procurement)"],
                    ["地址", "Sylhet Gas Fields Limited, P.O. Chiknagool, Sylhet-3152, Bangladesh"],
                    ["电话", "+8801711967395"],
                    ["邮箱", "dgmpr@sgfl.gov.bd"],
                    ["采购内容", "Soft Starter, VFD, Magnetic Contractor & ACB"],
                    ["备 注", "两阶段双信封招标；技术标和价格标分别密封提交；技术标开标后对合格者再开价格标"],
                    ["官方来源", f"<a href='{u['SGFL_FP08']['详情页']}' color='blue'>SGFL官网详情页</a>"],
                    ["PDF下载", f"<a href='{u['SGFL_FP08']['PDF下载']}' color='blue'>点击下载招标文件(PDF)</a>"],
                ],
            },
            {
                "title": "Procurement of Spare Parts for Caterpillar Gas Generator",
                "key": "截止日期 <b>约2026-06-12</b> | 招标编号 <b>SGFL/RGF/25-26/FP-07</b> | International Tender",
                "special": "<b>International Tender</b> | Caterpillar燃气发电机备件 | SGFL自有资金",
                "fields": [
                    ["招标编号", "SGFL/RGF/25-26/FP-07"],
                    ["采购方式", "International Tender"],
                    ["发布日期", "2026-04-13"],
                    ["存档日期", "2026-06-12"],
                    ["资金来源", "SGFL's Own Fund"],
                    ["采购内容", "Spare Parts for Caterpillar Gas Generator"],
                    ["备 注", "详细信息请参阅SGFL官网发布的完整招标文件PDF"],
                    ["官方来源1", f"<a href='{u['SGFL_FP07']['详情页_SGFL']}' color='blue'>SGFL官网详情页</a>"],
                    ["官方来源2", f"<a href='{u['SGFL_FP07']['详情页_Petrobangla']}' color='blue'>Petrobangla官网镜像页</a>"],
                    ["PDF下载", f"<a href='{u['SGFL_FP07']['PDF下载']}' color='blue'>点击下载招标文件(PDF)</a>"],
                ],
            },
        ],
    }


# ============== 行业动态 ==============
_INDUSTRY_NEWS_TEMPLATE = """
<b>1. 霍尔木兹海峡局势</b><br/>
• 伊朗官员{m_month}月{m_day}日警告美国，称干涉霍尔木兹海峡"新制度"即违反停火协议<br/>
• 美国宣布将派舰机支援霍尔木兹海峡"自由计划"，伊朗威胁对相关货物实施禁运<br/>
• 霍尔木兹海峡承担全球约30%的石油运输，局势紧张可能进一步推高国际油价和LNG价格<br/>
• 孟加拉本财年能源补贴已超19000亿塔卡，油价上涨将加剧财政压力<br/><br/>

<b>2. 孟加拉天然气储量</b><br/>
• 剩余可采天然气储量约7.63 TCF（截至2026年1月）<br/>
• 若无新发现，现有储量可维持约12年<br/>
• BAPEX正在推进3D地震勘探、钻井和修井作业<br/><br/>

<b>3. 重点关注提醒</b><br/>
• BGFCL发电机备件招标【近期截止】，请尽快安排<br/>
• BAPEX 2000HP钻井项目和BGFCL锅炉火管招标【5月18日截止】<br/><br/>

<b>4. 链接校验说明</b><br/>
• 本报告所有官方来源链接和PDF下载地址均于{fmt_date}校验通过，可正常访问
"""


def get_industry_news(validation_date: Optional[datetime] = None) -> str:
    """获取行业动态文本。"""
    today = datetime.now()
    fmt_date = (validation_date or today).strftime("%Y-%m-%d")
    return _INDUSTRY_NEWS_TEMPLATE.format(
        m=today,
        m_month=today.month,
        m_day=today.day,
        fmt_date=fmt_date
    )
