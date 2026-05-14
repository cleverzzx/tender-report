#!/bin/bash
# 孟加拉石油标讯报告一键生成脚本

cd "$(dirname "$0")"

# 优先使用 .venv，回退到 venv
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "错误: 未找到虚拟环境 (.venv 或 venv)"
    exit 1
fi

python main.py
