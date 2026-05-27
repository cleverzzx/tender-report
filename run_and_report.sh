#!/bin/bash
# 孟加拉标讯 — 运行并输出结果路径供 cron 使用
set -e

cd "$(dirname "$0")"
source .venv/bin/activate

# 运行报告生成
python main.py --no-email 2>&1

# 找到最新的 PDF
latest_pdf=$(ls -t reports/孟加拉标讯报告_*.pdf 2>/dev/null | head -1)
if [ -z "$latest_pdf" ]; then
    echo "ERROR: 未生成PDF"
    exit 1
fi

# 输出绝对路径和摘要供agent使用
abs_path="$(cd "$(dirname "$latest_pdf")" && pwd)/$(basename "$latest_pdf")"
echo ""
echo "---TENDER_RESULT---"
echo "PDF_PATH=$abs_path"
echo "---TENDER_END---"
