# MarketRadar Windows 任务计划程序配置脚本
# 
# 使用方法:
#   1. 以管理员身份运行 PowerShell
#   2. 修改 $ProjectDir 为你的项目路径
#   3. 运行: .\setup_windows_tasks.ps1

# ============================================
# 配置项
# ============================================

# 项目路径 (修改为你的实际路径)
$ProjectDir = "D:\AIProjects\MarketRadar"

# Python 解释器路径
$PythonExe = "python.exe"  # 或者完整路径如 "C:\Python39\python.exe"

# 日志目录
$LogDir = "$ProjectDir\logs"

# ============================================
# 创建日志目录
# ============================================

if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
    Write-Host "✓ 创建日志目录: $LogDir" -ForegroundColor Green
}

# ============================================
# 删除已存在的任务
# ============================================

$TaskNames = @(
    "MarketRadar_Premarket",
    "MarketRadar_Intraday_10",
    "MarketRadar_Intraday_14",
    "MarketRadar_Postmarket"
)

foreach ($TaskName in $TaskNames) {
    $Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($Task) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "✓ 删除已存在任务: $TaskName" -ForegroundColor Yellow
    }
}

# ============================================
# 创建任务 1: 盘前流程 (09:00)
# ============================================

$Action = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument "run_daily_pipeline.py --mode premarket" `
    -WorkingDirectory $ProjectDir

$Trigger = New-ScheduledTaskTrigger `
    -Weekly `
    -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday `
    -At 09:00

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable

Register-ScheduledTask `
    -TaskName "MarketRadar_Premarket" `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "MarketRadar 盘前流程: 采集信号 → 解码 → 判断机会" `
    -Force | Out-Null

Write-Host "✓ 创建任务: MarketRadar_Premarket (周一到周五 09:00)" -ForegroundColor Green

# ============================================
# 创建任务 2: 盘中流程 (10:00)
# ============================================

$Action = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument "run_daily_pipeline.py --mode intraday" `
    -WorkingDirectory $ProjectDir

$Trigger = New-ScheduledTaskTrigger `
    -Weekly `
    -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday `
    -At 10:00

Register-ScheduledTask `
    -TaskName "MarketRadar_Intraday_10" `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "MarketRadar 盘中流程: 更新价格 → 检查止损止盈" `
    -Force | Out-Null

Write-Host "✓ 创建任务: MarketRadar_Intraday_10 (周一到周五 10:00)" -ForegroundColor Green

# ============================================
# 创建任务 3: 盘中流程 (14:00)
# ============================================

$Trigger = New-ScheduledTaskTrigger `
    -Weekly `
    -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday `
    -At 14:00

Register-ScheduledTask `
    -TaskName "MarketRadar_Intraday_14" `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "MarketRadar 盘中流程: 更新价格 → 检查止损止盈" `
    -Force | Out-Null

Write-Host "✓ 创建任务: MarketRadar_Intraday_14 (周一到周五 14:00)" -ForegroundColor Green

# ============================================
# 创建任务 4: 盘后流程 (15:30)
# ============================================

$Action = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument "run_daily_pipeline.py --mode postmarket" `
    -WorkingDirectory $ProjectDir

$Trigger = New-ScheduledTaskTrigger `
    -Weekly `
    -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday `
    -At 15:30

Register-ScheduledTask `
    -TaskName "MarketRadar_Postmarket" `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "MarketRadar 盘后流程: 复盘归因 → 更新知识库" `
    -Force | Out-Null

Write-Host "✓ 创建任务: MarketRadar_Postmarket (周一到周五 15:30)" -ForegroundColor Green

# ============================================
# 显示已创建的任务
# ============================================

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "已创建的任务:" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Get-ScheduledTask | Where-Object { $_.TaskName -like "MarketRadar_*" } | Format-Table TaskName, State, @{Label="NextRunTime"; Expression={$_.Triggers[0].StartBoundary}}

Write-Host ""
Write-Host "日志位置:" -ForegroundColor Cyan
Write-Host "  - 盘前: $LogDir\cron_premarket.log" -ForegroundColor White
Write-Host "  - 盘中: $LogDir\cron_intraday.log" -ForegroundColor White
Write-Host "  - 盘后: $LogDir\cron_postmarket.log" -ForegroundColor White

Write-Host ""
Write-Host "管理任务:" -ForegroundColor Cyan
Write-Host "  - 查看任务: Get-ScheduledTask | Where-Object { `$_.TaskName -like 'MarketRadar_*' }" -ForegroundColor White
Write-Host "  - 启动任务: Start-ScheduledTask -TaskName 'MarketRadar_Premarket'" -ForegroundColor White
Write-Host "  - 停止任务: Stop-ScheduledTask -TaskName 'MarketRadar_Premarket'" -ForegroundColor White
Write-Host "  - 删除任务: Unregister-ScheduledTask -TaskName 'MarketRadar_Premarket' -Confirm:`$false" -ForegroundColor White

# ============================================
# 测试运行
# ============================================

Write-Host ""
$TestRun = Read-Host "是否测试运行盘前流程? (y/n)"

if ($TestRun -eq "y" -or $TestRun -eq "Y") {
    Write-Host "开始测试..." -ForegroundColor Yellow
    Set-Location $ProjectDir
    & $PythonExe run_daily_pipeline.py --mode premarket --limit 5
}
