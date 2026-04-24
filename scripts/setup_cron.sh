#!/bin/bash
# MarketRadar 定时任务配置脚本
# 
# 使用方法:
#   1. 修改 PROJECT_DIR 为你的项目路径
#   2. 运行: bash setup_cron.sh
#   3. 检查: crontab -l

# ============================================
# 配置项
# ============================================

# 项目路径 (修改为你的实际路径)
PROJECT_DIR="/mnt/d/AIProjects/MarketRadar"

# Python 解释器路径
PYTHON_BIN="/usr/bin/python3"

# 日志目录
LOG_DIR="$PROJECT_DIR/logs"

# ============================================
# 创建日志目录
# ============================================

mkdir -p "$LOG_DIR"

# ============================================
# 生成 crontab 配置
# ============================================

CRON_FILE="/tmp/marketradar_cron.txt"

cat > "$CRON_FILE" << EOF
# MarketRadar 自动化定时任务
# 生成时间: $(date)

# 盘前流程 (周一到周五 09:00)
# 采集隔夜信号 → 解码 → 判断机会
0 9 * * 1-5 cd $PROJECT_DIR && $PYTHON_BIN run_daily_pipeline.py --mode premarket >> $LOG_DIR/cron_premarket.log 2>&1

# 盘中流程 (周一到周五 10:00, 14:00)
# 更新持仓价格 → 检查止损止盈
0 10,14 * * 1-5 cd $PROJECT_DIR && $PYTHON_BIN run_daily_pipeline.py --mode intraday >> $LOG_DIR/cron_intraday.log 2>&1

# 盘后流程 (周一到周五 15:30)
# 复盘归因 → 更新知识库
30 15 * * 1-5 cd $PROJECT_DIR && $PYTHON_BIN run_daily_pipeline.py --mode postmarket >> $LOG_DIR/cron_postmarket.log 2>&1

# 日志清理 (每周日 00:00)
# 删除 30 天前的日志
0 0 * * 0 find $LOG_DIR -name "*.log" -mtime +30 -delete

EOF

echo "✓ Crontab 配置已生成: $CRON_FILE"
echo ""
cat "$CRON_FILE"
echo ""

# ============================================
# 安装 crontab
# ============================================

read -p "是否安装到 crontab? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
    # 备份现有 crontab
    crontab -l > /tmp/crontab_backup_$(date +%Y%m%d_%H%M%S).txt 2>/dev/null
    
    # 安装新 crontab
    crontab "$CRON_FILE"
    
    echo "✓ Crontab 已安装"
    echo ""
    echo "当前 crontab 配置:"
    crontab -l
    echo ""
    echo "日志位置:"
    echo "  - 盘前: $LOG_DIR/cron_premarket.log"
    echo "  - 盘中: $LOG_DIR/cron_intraday.log"
    echo "  - 盘后: $LOG_DIR/cron_postmarket.log"
else
    echo "✗ 已取消安装"
    echo ""
    echo "手动安装方法:"
    echo "  crontab $CRON_FILE"
fi

# ============================================
# 测试运行
# ============================================

echo ""
read -p "是否测试运行盘前流程? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
    echo "开始测试..."
    cd "$PROJECT_DIR"
    $PYTHON_BIN run_daily_pipeline.py --mode premarket --limit 5
fi
