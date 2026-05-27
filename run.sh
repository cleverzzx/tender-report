#!/bin/bash
# 孟加拉标讯报告 — 一键运行
# 用法: ./run.sh                  # 生成PDF+发邮件
#       ./run.sh --no-email       # 只生成PDF
#       ./run.sh --scrape         # 爬取+生成
#       ./run.sh --validate-only  # 仅校验链接

cd "$(dirname "$0")" || exit
source .venv/bin/activate
exec python main.py --no-email "$@"
