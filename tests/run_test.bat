@echo off
echo ============================================================
echo CNKI MCP 服务测试
echo ============================================================
echo.

cd /d "%~dp0"

echo 检查 Python 环境...
python --version
if errorlevel 1 (
    echo 错误: 未找到 Python
    pause
    exit /b 1
)

echo.
echo 检查依赖包...
python -c "import mcp" 2>nul
if errorlevel 1 (
    echo 警告: 未安装 mcp 包
    echo 正在安装...
    pip install mcp
)

python -c "import playwright" 2>nul
if errorlevel 1 (
    echo 警告: 未安装 playwright 包
    echo 正在安装...
    pip install playwright
    playwright install chromium
)

echo.
echo ============================================================
echo 开始运行测试...
echo ============================================================
echo.

python test_complete.py

echo.
echo ============================================================
echo 测试完成
echo ============================================================
pause

