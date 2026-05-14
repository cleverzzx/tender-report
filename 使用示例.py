# -*- coding: utf-8 -*-
"""
孟加拉标讯报告生成工具 - 使用示例

本地 Python 调用方法：
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_tender_report import generate_pdf, get_tender_data, send_email


def main():
    # 方式1: 获取标讯数据（含爬取尝试）
    print("=== 获取标讯数据 ===")
    tenders = get_tender_data()
    total = sum(len(v) for v in tenders.values())
    print(f"共 {total} 条标讯:")
    for company in ["BAPEX", "BGFCL", "SGFL"]:
        for t in tenders.get(company, []):
            print(f"  [{company}] {t['title'][:60]}...")

    # 方式2: 生成PDF报告
    print("\n=== 生成报告 ===")
    output_path = generate_pdf(tenders=tenders)
    print(f"报告已生成: {output_path}")

    # 方式3: 发送邮件（需先配置环境变量）
    # send_email(output_path)


if __name__ == "__main__":
    main()
