#!/bin/bash
# 实盘信号监控启动脚本

echo "=========================================="
echo "MarketRadar 实盘信号监控系统"
echo "=========================================="
echo ""

# 检查Python环境
if ! command -v python &> /dev/null; then
    echo "[错误] 未找到Python，请先安装Python 3.8+"
    exit 1
fi

# 检查配置文件
if [ ! -f "config/llm_config.local.yaml" ]; then
    echo "[错误] 未找到LLM配置文件: config/llm_config.local.yaml"
    echo "[提示] 请先配置DeepSeek API密钥"
    exit 1
fi

# 创建输出目录
mkdir -p live_validation

echo "[启动] 开始实盘监控..."
echo ""

# 运行监控（单次模式）
python live_signal_monitor.py "$@"

echo ""
echo "[完成] 监控任务结束"
