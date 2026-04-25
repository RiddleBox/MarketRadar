@echo off
REM 实盘信号监控启动脚本 (Windows)

echo ==========================================
echo MarketRadar 实盘信号监控系统
echo ==========================================
echo.

REM 检查Python环境
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python，请先安装Python 3.8+
    exit /b 1
)

REM 检查配置文件
if not exist "config\llm_config.local.yaml" (
    echo [错误] 未找到LLM配置文件: config\llm_config.local.yaml
    echo [提示] 请先配置DeepSeek API密钥
    exit /b 1
)

REM 创建输出目录
if not exist "live_validation" mkdir live_validation

echo [启动] 开始实盘监控...
echo.

REM 运行监控
python live_signal_monitor.py %*

echo.
echo [完成] 监控任务结束
