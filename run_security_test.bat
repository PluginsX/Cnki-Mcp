@echo off

rem 知网安全验证测试脚本
rem 使用项目虚拟环境运行测试

echo 正在运行知网安全验证测试...
echo ================================

rem 检查虚拟环境是否存在
if not exist "venv\Scripts\activate.bat" (
    echo 错误: 虚拟环境不存在！
    echo 请先创建虚拟环境并安装依赖
    pause
    exit /b 1
)

rem 激活虚拟环境
echo 激活虚拟环境...
call venv\Scripts\activate.bat

rem 检查依赖
pip list | findstr "playwright opencv-python numpy"
if errorlevel 1 (
    echo 错误: 缺少必要的依赖！
    echo 请运行: pip install playwright opencv-python numpy
    pause
    exit /b 1
)

rem 运行测试
echo 运行安全验证测试...
python test_security_verification.py

rem 保存退出码
set "EXIT_CODE=%errorlevel%"

rem 退出虚拟环境
deactivate

echo ================================
if %EXIT_CODE% equ 0 (
    echo 测试成功完成！
) else (
    echo 测试失败！
)

pause
