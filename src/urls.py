# -*- coding: utf-8 -*-
"""标讯 URL 数据库 —— 官方链接和列表页地址"""

from typing import Dict

# ============== 官方链接数据库 ==============
# 每条标讯的详情页 + PDF 下载地址
OFFICIAL_URLS: Dict[str, Dict[str, str]] = {
    "BAPEX_1308": {
        "详情页": (
            "https://bapex.com.bd/pages/tenders/"
            "2nd-extension-of-international-tender-tender-no-bapexadminintten-13082026-"
            "closing-date-puncw3-69df2735e3444b2e09d877cb"
        ),
        "PDF下载": (
            "https://objectstorage.ap-dcc-gazipur-1.oraclecloud15.com/n/axvjbnqprylg/"
            "b/V2Ministry/o/office-bapex/2026/3/9864ccac-7895-48b0-927d-56dc40a02d53.pdf"
        ),
    },
    "BGFCL_234": {
        "详情页": (
            "https://bgfcl.portal.gov.bd/pages/tenders/"
            "procurement-of-mechanical-spare-parts-of-fg-wilson-perkins-generator-engine-"
            "model-4006-23trsl-0wbeb5-69d4dce58e1b33330b2fc495"
        ),
        "PDF下载": (
            "https://objectstorage.ap-dcc-gazipur-1.oraclecloud15.com/n/axvjbnqprylg/"
            "b/V2Ministry/o/office-bgfcl/2026/3/c6f31cf1-7b4d-46fa-855b-5154853bcf29.pdf"
        ),
    },
    "BGFCL_239": {
        "详情页": (
            "https://petrobangla.org.bd/pages/tenders/"
            "%E0%A6%AB%E0%A6%BE%E0%A7%9F%E0%A6%BE%E0%A6%B0-%E0%A6%9F%E0%A6%BF%E0%A6%89%E0%A6%AC-"
            "%E0%A6%95%E0%A7%8D%E0%A6%B0%E0%A7%9F%E0%A7%87%E0%A6%B0-%E0%A6%86%E0%A6%A8%E0%A7%8D%E0%A6%A4%E0%A6%B0%E0%A7%8D%E0%A6%9C%E0%A6%BE%E0%A6%A4%E0%A6%BF%E0%A6%95-"
            "%E0%A6%A6%E0%A6%B0%E0%A6%AA%E0%A6%A4%E0%A7%8D%E0%A6%B0-bgfclgoodsfp239-"
            "%E0%A6%AC%E0%A6%BF%E0%A6%9C%E0%A6%BF%E0%A6%8F%E0%A6%AB%E0%A6%B8%E0%A6%BF%E0%A6%8F%E0%A6%B2-ilguki-69d4b39608aced6888358072"
        ),
        "PDF下载": (
            "https://objectstorage.ap-dcc-gazipur-1.oraclecloud15.com/n/axvjbnqprylg/"
            "b/V2Ministry/o/office-bgfcl/2026/3/fd32de87-d048-43a3-93c8-25b8dff1133b.pdf"
        ),
    },
    "SGFL_FP08": {
        "详情页": (
            "https://sgfl.gov.bd/pages/tenders/"
            "international-tender-notice-procurement-of-soft-starter-vfd-magnetic-contractor-"
            "acb-pw0ipl-69f03f238864d0208af3dbb7"
        ),
        "PDF下载": (
            "https://objectstorage.ap-dcc-gazipur-1.oraclecloud15.com/n/axvjbnqprylg/"
            "b/V2Ministry/o/office-sgfl/2026/3/cb1775cb-4cb0-43f1-b2c2-1530739488cb.pdf"
        ),
    },
    "SGFL_FP07": {
        "详情页_SGFL": (
            "https://sgfl.gov.bd/pages/tenders/"
            "international-tender-notice-procurement-of-spare-parts-for-caterpillar-gas-"
            "generator-ts00fl-69dcb1a4508fd61cddc8f90b"
        ),
        "详情页_Petrobangla": (
            "https://petrobangla.org.bd/pages/tenders/"
            "%E0%A6%B8%E0%A7%8D%E0%A6%AA%E0%A7%87%E0%A7%9F%E0%A6%BE%E0%A6%B0-"
            "%E0%A6%AA%E0%A6%BE%E0%A6%B0%E0%A7%8D%E0%A6%9F%E0%A6%B8-%E0%A6%95%E0%A7%8D%E0%A6%B0%E0%A7%9F%E0%A7%87%E0%A6%B0-"
            "%E0%A6%9C%E0%A6%A8%E0%A7%8D%E0%A6%AF-%E0%A6%86%E0%A6%A8%E0%A7%8D%E0%A6%A4%E0%A6%B0%E0%A7%8D%E0%A6%9C%E0%A6%BE%E0%A6%A4%E0%A6%BF%E0%A6%95-"
            "%E0%A6%A6%E0%A6%B0%E0%A6%AA%E0%A6%A4%E0%A7%8D%E0%A6%B0-rgf25-26fp-07-"
            "%E0%A6%8F%E0%A6%B8%E0%A6%9C%E0%A6%BF%E0%A6%8F%E0%A6%AB%E0%A6%8F%E0%A6%B2-qh0epg-69df6822699eb2a64080b176"
        ),
        "PDF下载": (
            "https://objectstorage.ap-dcc-gazipur-1.oraclecloud15.com/n/axvjbnqprylg/"
            "b/V2Ministry/o/office-sgfl/2026/3/7bc64fc4-0e7f-45d5-9ddc-8274593ecea2.pdf"
        ),
    },
}

# ============== 爬取目标 —— 标讯列表页 ==============
LISTING_URLS: Dict[str, str] = {
    "BAPEX": "https://bapex.com.bd/pages/tenders",
    "Petrobangla": "https://petrobangla.org.bd/pages/tenders",
    "SGFL": "https://sgfl.gov.bd/pages/tenders",
    "BGFCL_portal": "https://bgfcl.portal.gov.bd/pages/tenders",
}
