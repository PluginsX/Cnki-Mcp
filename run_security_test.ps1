<#
知网安全验证测试脚本 (PowerShell 版本)

功能：
1. 打开知网首页
2. 检测并处理安全验证
3. 验证验证是否成功
4. 提供详细的测试结果
#>

Write-Host "正在运行知网安全验证测试..."
Write-Host "==============================="

# 检查虚拟环境是否存在
if (-not (Test-Path "venv\Scripts\activate.ps1")) {
    Write-Host "错误: 虚拟环境不存在！" -ForegroundColor Red
    Write-Host "请先创建虚拟环境并安装依赖"
    Read-Host "按 Enter 键退出..."
    exit 1
}

# 激活虚拟环境
Write-Host "激活虚拟环境..."
& venv\Scripts\Activate.ps1

# 检查依赖
$deps = @("playwright", "opencv-python", "numpy")
$missing = @()

foreach ($dep in $deps) {
    $result = pip list | Select-String $dep
    if (-not $result) {
        $missing += $dep
    }
}

if ($missing.Count -gt 0) {
    Write-Host "错误: 缺少必要的依赖！" -ForegroundColor Red
    Write-Host "请运行: pip install $($missing -join ' ')"
    Read-Host "按 Enter 键退出..."
    exit 1
}

# 运行测试
Write-Host "运行安全验证测试..."
python test_security_verification.py

# 保存退出码
$exitCode = $LASTEXITCODE

# 退出虚拟环境
deactivate

Write-Host "==============================="
if ($exitCode -eq 0) {
    Write-Host "测试成功完成！" -ForegroundColor Green
} else {
    Write-Host "测试失败！" -ForegroundColor Red
}

Read-Host "按 Enter 键退出..."
