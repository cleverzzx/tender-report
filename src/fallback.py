# -*- coding: utf-8 -*-
"""标讯回退数据 —— 爬取失败时使用的硬编码标讯"""

from typing import Any, Dict, List

from src.urls import OFFICIAL_URLS


def get_fallback_tenders() -> Dict[str, List[Dict[str, Any]]]:
    """返回硬编码的标讯数据，作为爬取失败时的回退。

    Returns:
        按公司分类的标讯字典 {"BAPEX": [...], "BGFCL": [...], "SGFL": [...]}
    """
    u = OFFICIAL_URLS
    return {
        "BAPEX": [
            {
                "title": "2000 HP AC-AC VFD Land Drilling Rig 交钥匙工程",
                "key": (
                    "截止日期 <b>2026-05-18 11:30</b> | "
                    "标书价格 <b>BDT 12,000 / USD 98</b> | "
                    "保证金 <b>USD 385,000</b>"
                ),
                "special": (
                    "<b>2nd Extension</b> | International Turn-Key Drilling Rig | "
                    "合同期662天 | 钻井深度≥5000米"
                ),
                "fields": [
                    ["招标编号", "BAPEX/Admin/Int/Ten-1308/2026 (2nd Extension)"],
                    ["采购方式", "International Turn-Key Tender"],
                    ["发布日期", "2026-01-28 / 2026-04-13"],
                    ["标书发售截止", "2026-05-17 15:00"],
                    ["投标截止日期", "2026-05-18 11:30"],
                    ["开标日期", "2026-05-18 12:30"],
                    ["标书价格", "BDT 12,000 或 USD 98 (不退)"],
                    ["投标保证金", "USD 385,000 (仅接受银行保函)"],
                    ["投标有效期", "180天"],
                    ["合同期", "662天"],
                    [
                        "采购内容",
                        (
                            "2000 HP AC-AC VFD型陆地钻井交钥匙工程：设计、工程、采购、供应、"
                            "安装、调试、测试及一口井钻井期间的全部维护服务，含强制备件，"
                            "钻井深度可达5000米以上"
                        ),
                    ],
                    ["联系人", "Md. Asad Ullah"],
                    ["职位", "General Manager (Admin.)"],
                    [
                        "备 注",
                        "这是第二次延期，其他条款和条件不变。此为当前最紧迫的大型钻井设备国际招标。",
                    ],
                    [
                        "官方来源",
                        f"<a href='{u['BAPEX_1308']['详情页']}' color='blue'>BAPEX官网详情页</a>",
                    ],
                    [
                        "PDF下载",
                        f"<a href='{u['BAPEX_1308']['PDF下载']}' color='blue'>点击下载招标文件(PDF)</a>",
                    ],
                ],
            }
        ],
        "BGFCL": [
            {
                "title": (
                    "Procurement of Mechanical Spare parts of FG Wilson (Perkins) "
                    "Generator Engine Model: 4006-23TRSL"
                ),
                "key": (
                    "截止日期 <b>2026-05-06 14:15</b> | "
                    "标书价格 <b>USD 50 / BDT 6,000</b> | "
                    "保证金 <b>USD 570 / BDT 70,000</b>"
                ),
                "special": (
                    "<b>International Re-Tender</b> | FG Wilson/Perkins发电机备件 | "
                    "交货期120天 | ISO认证要求"
                ),
                "fields": [
                    ["招标编号", "BGFCL/GOODS(FP)/234(R1) Dated April 05, 2026"],
                    ["采购方式", "Foreign/International Tender (Re-Tender)"],
                    ["发布日期", "2026-04-05 / 2026-04-07"],
                    ["截止日期", "2026-05-06 14:15"],
                    ["开标日期", "2026-05-06 14:30"],
                    ["标书价格", "BDT 6,000 或 USD 50 (不退)"],
                    ["投标保证金", "USD 570 或 BDT 70,000 (仅接受银行保函)"],
                    [
                        "采购内容",
                        "FG Wilson (Perkins) Generator Engine Model: 4006-23TRSL 机械备件",
                    ],
                    ["交货时间", "L/C开立后120天"],
                    [
                        "投标人资格",
                        (
                            "除以色列外所有国家的知名制造商/供应商，需满足：5年以上经验，"
                            "制造商需10年以上经验，持有ISO 9001/14001/OHSAS 18001认证"
                        ),
                    ],
                    ["联系人", "Engr. M. K. Masuk"],
                    ["职位", "General Manager (Technical Services)"],
                    ["电话", "+8****30 093679"],
                    ["邮箱", "prbgfci@gmail.com / gmts@bafdl.gov.bd"],
                    [
                        "备 注",
                        "此为重新招标，技术标与价格标双信封提交，仅银行保函接受。【后天截止】",
                    ],
                    [
                        "官方来源",
                        f"<a href='{u['BGFCL_234']['详情页']}' color='blue'>BGFCL官网详情页</a>",
                    ],
                    [
                        "PDF下载",
                        f"<a href='{u['BGFCL_234']['PDF下载']}' color='blue'>点击下载招标文件(PDF)</a>",
                    ],
                ],
            },
            {
                "title": "International Tender - Procurement of Fire Tube Pipe for Oil Bath Heater",
                "key": (
                    "截止日期 <b>2026-05-18 14:15</b> | "
                    "标书价格 <b>USD 50 / BDT 6,000</b> | "
                    "保证金 <b>USD 940 / BDT 115,000</b>"
                ),
                "special": (
                    "<b>International Tender</b> | One Stage Two envelope | "
                    "交货期120天 | ISO认证要求"
                ),
                "fields": [
                    ["招标编号", "BGFCL/GOODS(FP)/239"],
                    ["采购方式", "Foreign/International Tender (One Stage Two envelope)"],
                    ["发布日期", "2026-04-06 / 2026-04-08"],
                    ["截止日期", "2026-05-18 14:15"],
                    ["开标日期", "2026-05-18 14:30"],
                    ["标书价格", "BDT 6,000 或 USD 50 (不退)"],
                    ["投标保证金", "USD 940 或 BDT 115,000 (仅接受银行保函)"],
                    ["采购内容", "Fire Tube Pipe for Oil Bath Heater (锅炉火管)"],
                    ["交货时间", "L/C开立后120天"],
                    [
                        "投标人资格",
                        (
                            "除以色列外所有国家的知名制造商/供应商，需满足：5年以上经验，"
                            "制造商需10年以上经验，持有ISO 9001/14001/OHSAS 18001认证"
                        ),
                    ],
                    ["联系人", "Engr. M. K. Masuk"],
                    ["职位", "General Manager (Technical Services)"],
                    ["电话", "+8****30 093679"],
                    ["邮箱", "prbgfd@gmail.com / dgmfp@bgfd.gov.bd"],
                    ["备 注", "技术标与价格标双信封提交，仅银行保函接受作为保证金"],
                    [
                        "官方来源",
                        f"<a href='{u['BGFCL_239']['详情页']}' color='blue'>Petrobangla/BGFCL官网详情页</a>",
                    ],
                    [
                        "PDF下载",
                        f"<a href='{u['BGFCL_239']['PDF下载']}' color='blue'>点击下载招标文件(PDF)</a>",
                    ],
                ],
            },
        ],
        "SGFL": [
            {
                "title": "Procurement of Soft Starter, VFD, Magnetic Contractor & ACB",
                "key": (
                    "截止日期 <b>2026-06-18 12:00</b> | "
                    "标书价格 <b>USD 98 / BDT 12,000</b> | "
                    "保证金 <b>USD 2,550 / BDT 310,000</b>"
                ),
                "special": (
                    "<b>International Procurement</b> | One Stage Two envelope Tendering | "
                    "有效期120天"
                ),
                "fields": [
                    ["招标编号", "SGFL/CFP/RCFP/CRU/25-26/FP-08"],
                    ["采购方式", "International Procurement (One Stage Two envelope)"],
                    ["发布日期", "2026-04-28"],
                    ["截止日期", "2026-06-18 12:00"],
                    ["开标日期", "2026-06-18 12:15"],
                    ["标书发售截止", "2026-06-17"],
                    ["标书价格", "BDT 12,000 或 USD 98 (不退)"],
                    ["投标保证金", "BDT 310,000 或 USD 2,550"],
                    ["联系人", "Ziaur Rahman Khan"],
                    ["职位", "Deputy General Manager (Procurement)"],
                    [
                        "地址",
                        "Sylhet Gas Fields Limited, P.O. Chiknagool, Sylhet-3152, Bangladesh",
                    ],
                    ["电话", "+880****7395"],
                    ["邮箱", "dgmpr@sgfl.gov.bd"],
                    ["采购内容", "Soft Starter, VFD, Magnetic Contractor & ACB"],
                    [
                        "备 注",
                        "两阶段双信封招标；技术标和价格标分别密封提交；技术标开标后对合格者再开价格标",
                    ],
                    [
                        "官方来源",
                        f"<a href='{u['SGFL_FP08']['详情页']}' color='blue'>SGFL官网详情页</a>",
                    ],
                    [
                        "PDF下载",
                        f"<a href='{u['SGFL_FP08']['PDF下载']}' color='blue'>点击下载招标文件(PDF)</a>",
                    ],
                ],
            },
            {
                "title": "Procurement of Spare Parts for Caterpillar Gas Generator",
                "key": (
                    "截止日期 <b>约2026-06-12</b> | "
                    "招标编号 <b>SGFL/RGF/25-26/FP-07</b> | International Tender"
                ),
                "special": (
                    "<b>International Tender</b> | Caterpillar燃气发电机备件 | SGFL自有资金"
                ),
                "fields": [
                    ["招标编号", "SGFL/RGF/25-26/FP-07"],
                    ["采购方式", "International Tender"],
                    ["发布日期", "2026-04-13"],
                    ["存档日期", "2026-06-12"],
                    ["资金来源", "SGFL's Own Fund"],
                    ["采购内容", "Spare Parts for Caterpillar Gas Generator"],
                    ["备 注", "详细信息请参阅SGFL官网发布的完整招标文件PDF"],
                    [
                        "官方来源1",
                        f"<a href='{u['SGFL_FP07']['详情页_SGFL']}' color='blue'>SGFL官网详情页</a>",
                    ],
                    [
                        "官方来源2",
                        f"<a href='{u['SGFL_FP07']['详情页_Petrobangla']}' color='blue'>Petrobangla官网镜像页</a>",
                    ],
                    [
                        "PDF下载",
                        f"<a href='{u['SGFL_FP07']['PDF下载']}' color='blue'>点击下载招标文件(PDF)</a>",
                    ],
                ],
            },
        ],
    }
