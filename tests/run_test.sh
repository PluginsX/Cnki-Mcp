#!/bin/bash

echo "============================================================"
echo "CNKI MCP 服务测试"
echo "============================================================"
echo ""

cd "$(dirname "$0")"

echo "检查 Python 环境..."
python3 --version
if [ $? -ne 0 ]; then
    echo "错误: 未找到 Python"
    exit 1
fi

echo ""
echo "检查依赖包..."
python3 -c "import mcp" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "警告: 未安装 mcp 包"
    echo "正在安装..."
    pip3 install mcp
fi

python3 -c "import playwright" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "警告: 未安装 playwright 包"
    echo "正在安装..."
    pip3 install playwright
    playwright install chromium
fi

echo ""
echo "============================================================"
echo "开始运行测试..."
echo "============================================================"
echo ""

python3 test_complete.py

echo ""
echo "============================================================"
echo "测试完成"
echo "============================================================"

