# MarketRadar 用户使用手册

> 版本: 2.0 | 更新日期: 2026-05-06

---

## 📋 目录

1. [快速开始](#快速开始)
2. [系统架构](#系统架构)
3. [核心功能](#核心功能)
4. [命令行工具](#命令行工具)
5. [数据说明](#数据说明)
6. [常见问题](#常见问题)
7. [高级配置](#高级配置)

---

## 🚀 快速开始

### 一键启动（推荐）

双击运行项目根目录的 `start.bat` 文件，系统会自动：
1. 检查环境
2. 启动调度器
3. 显示功能菜单

### 手动启动

```bash
# 1. 进入项目目录
cd D:\AIProjects\MarketRadar

# 2. 启动调度器（后台运行）
python -m m7_scheduler.cli start --background

# 3. 查看状态
python -m m7_scheduler.cli status
```

### 停止系统

```bash
python -m m7_scheduler.cli stop
```

---

## 🏗️ 系统架构

MarketRadar 采用模块化设计，各模块职责如下：

```
┌─────────────────────────────────────────────────────────────┐
│                      M7 调度器 (核心)                        │
│              自动管理所有任务的执行和调度                     │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│  信号处理链   │      │  M12 扫描器   │      │  M9 模拟盘   │
│  M0→M1→M2    │      │  机会捕捉     │      │  纸上交易    │
│  →M3→M4      │      │              │      │              │
└──────────────┘      └──────────────┘      └──────────────┘
        │                     │                     │
        └─────────────────────┴─────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
            ┌──────────────┐    ┌──────────────┐
            │  M6 复盘引擎  │    │  M10 情绪监控 │
            │  归因分析     │    │  市场情绪     │
            └──────────────┘    └──────────────┘
```

### 模块说明

| 模块 | 名称 | 功能 |
|------|------|------|
| **M0** | 信息收集器 | 采集新闻、公告、财报等原始信息 |
| **M1** | 信号解码器 | 将原始信息解码为结构化信号 |
| **M2** | 知识存储 | 存储信号、案例、因果图谱 |
| **M3** | 判断引擎 | 评估信号质量和可信度 |
| **M4** | 行动设计器 | 生成具体交易计划 |
| **M6** | 复盘引擎 | 收盘后归因分析，提取教训 |
| **M7** | 调度器 | 统一任务调度和时间管理 |
| **M9** | 模拟交易 | 纸上交易，跟踪持仓和盈亏 |
| **M10** | 情绪监控 | 采集恐贪指数、北向资金等情绪指标 |
| **M12** | 机会捕捉器 | 全市场价格扫描，发现异动机会 |

---

## 🎯 核心功能

### 1. 自动化调度系统

调度器会自动执行以下任务：

#### 全天候任务
- **信号处理管道** (30分钟/次)
  - 扫描 `data/incoming/` 目录
  - 处理新增的信号文件
  - 执行 M0→M1→M2→M3→M4 完整流程

- **新闻采集** (15分钟/次)
  - 东方财富新闻
  - 财联社快讯
  - 自动去重和存储

#### 交易时段任务
- **价格更新** (10分钟/次, 09:25-15:05)
  - 更新模拟仓位价格
  - 检查止损止盈条件
  - 自动执行平仓

- **M12 盘中扫描** (10分钟/次)
  - A股: 09:30-15:00
  - 港股: 09:30-16:00
  - 美股: 21:30-04:00
  - 实时发现价格异动

- **情绪采集** (30分钟/次, 09:00-22:00)
  - 恐贪指数
  - 北向资金流向
  - 热搜榜单

#### 每日定时任务
- **盘前扫描** (每日一次)
  - A股: 09:00
  - 港股: 09:00
  - 美股: 21:00
  - 分析隔夜信号，生成开盘策略

- **盘后扫描** (每日一次)
  - A股: 15:30
  - 港股: 16:30
  - 美股: 05:00
  - 全量扫描，扩展监控池

- **每日复盘** (15:30-23:59)
  - 分析当日交易
  - 归因盈亏原因
  - 提取经验教训

### 2. M12 机会捕捉器

M12 是核心的机会发现模块，工作流程：

```
价格数据 → 异动检测 → 反向溯因 → 趋势判断 → 机会生成
```

**扫描类型：**
- **盘中扫描**: 监控池内股票，10分钟一次
- **盘前扫描**: 分析隔夜信号，制定开盘策略
- **盘后扫描**: 全市场扫描，发现新机会

**输出位置：**
- 扫描结果: `data/m12_scan_results.json`
- 机会详情: `data/opportunities/`
- 交易计划: `data/opportunities/plan_*.json`

### 3. 信号处理链

完整的信号处理流程：

```
1. 用户放入信号文件到 data/incoming/
   ├─ 支持格式: .txt, .md, .json
   └─ 内容: 新闻、公告、观察等

2. M0 收集器读取文件
   └─ 标准化格式

3. M1 解码器提取结构化信息
   ├─ 事件类型
   ├─ 影响标的
   └─ 时间范围

4. M2 存储到知识库
   ├─ 信号库 (data/signals/signal_store.db)
   └─ 因果图谱

5. M3 判断引擎评估
   ├─ 信号质量
   ├─ 可信度
   └─ 优先级

6. M4 生成行动计划
   ├─ 交易方向
   ├─ 仓位建议
   └─ 止损止盈
```

### 4. 模拟交易 (M9)

**功能：**
- 纸上交易，不涉及真实资金
- 自动跟踪持仓和盈亏
- 支持止损止盈自动平仓

**数据位置：**
- 持仓数据: `data/portfolio.db`
- 交易日志: `data/paper_trade_log.json`

**手动交易：**
```python
from m9_paper_trader.paper_trader import PaperTrader

trader = PaperTrader()

# 买入
trader.buy(symbol="000001.SZ", shares=100, price=10.5)

# 卖出
trader.sell(symbol="000001.SZ", shares=50, price=11.0)

# 查看持仓
positions = trader.get_positions()
```

### 5. Web Dashboard

可视化监控面板，实时查看系统状态。

**启动方式：**
```bash
python -m pipeline.dashboard
```

**访问地址：**
```
http://localhost:8000
```

**功能：**
- 调度器状态
- 任务执行历史
- 持仓和盈亏
- 最新机会列表
- 信号处理记录

---

## 🛠️ 命令行工具

### M7 调度器 CLI

```bash
# 启动调度器（后台）
python -m m7_scheduler.cli start --background

# 启动调度器（前台，可看到实时输出）
python -m m7_scheduler.cli start

# 查看状态
python -m m7_scheduler.cli status

# 手动触发任务
python -m m7_scheduler.cli run <task_name>

# 停止调度器
python -m m7_scheduler.cli stop
```

**可用任务名：**
- `signal_pipeline` - 信号处理管道
- `price_update` - 价格更新
- `daily_review` - 每日复盘
- `news_collect` - 新闻采集
- `sentiment_collect` - 情绪采集
- `m12_a_share_scan` - A股扫描
- `m12_hk_scan` - 港股扫描
- `m12_us_scan` - 美股扫描
- `m12_premarket_a_share` - A股盘前
- `m12_postmarket_a_share` - A股盘后
- (其他市场的盘前/盘后任务类似)

**自定义参数：**
```bash
python -m m7_scheduler.cli start --background \
  --tick 30 \                # 调度间隔（秒）
  --signal-interval 30 \     # 信号处理间隔（分钟）
  --price-interval 10 \      # 价格更新间隔（分钟）
  --news-interval 15 \       # 新闻采集间隔（分钟）
  --no-news                  # 禁用新闻采集
```

### M12 扫描器 CLI

```bash
# 盘中扫描（监控池）
python -m m12_opportunity_catcher.run_intraday_scan --market a_share

# 盘前扫描（隔夜信号）
python -m m12_opportunity_catcher.run_premarket_scan --market a_share

# 盘后扫描（全市场）
python -m m12_opportunity_catcher.run_postmarket_scan --market a_share

# 市场选项: a_share, hk, us
```

### Dashboard CLI

```bash
# 启动 Web 面板
python -m pipeline.dashboard

# 指定端口
python -m pipeline.dashboard --port 8080
```

---

## 📊 数据说明

### 目录结构

```
data/
├── incoming/              # 待处理的信号文件（用户放入）
├── signals/               # 已处理的信号
│   └── signal_store.db    # 信号数据库
├── opportunities/         # M12 发现的机会
│   ├── opportunities_*.json
│   └── plan_*.json        # 交易计划
├── portfolio.db           # 模拟持仓数据库
├── paper_trade_log.json   # 交易日志
├── stock_universe.json    # 股票池配置
├── scheduler_state.json   # 调度器状态
├── daily_reports/         # 每日复盘报告
├── decisions/             # 决策记录
└── logs/                  # 系统日志
    └── scheduler.log      # 调度器日志
```

### 关键文件说明

#### 1. `stock_universe.json` - 股票池配置

定义 M12 扫描的股票范围：

```json
{
  "a_share": {
    "intraday": ["000001.SZ", "600000.SH"],  // 盘中监控
    "postmarket": ["all"]                     // 盘后全扫
  },
  "hk": {
    "intraday": ["00700.HK", "09988.HK"],
    "postmarket": ["all"]
  }
}
```

#### 2. `opportunities_*.json` - 机会记录

M12 扫描发现的机会：

```json
{
  "scan_id": "m12_a_share_20260506_093000",
  "timestamp": "2026-05-06T09:30:00",
  "market": "a_share",
  "opportunities": [
    {
      "symbol": "000001.SZ",
      "name": "平安银行",
      "anomaly_type": "volume_surge",  // 异动类型
      "score": 8.5,                    // 评分
      "reason": "成交量突增3倍...",
      "trend_stage": "突破",
      "action_plan": {
        "direction": "LONG",
        "entry_price": 10.5,
        "stop_loss": 10.0,
        "take_profit": 11.5
      }
    }
  ]
}
```

#### 3. `paper_trade_log.json` - 交易日志

记录所有模拟交易：

```json
[
  {
    "timestamp": "2026-05-06T10:00:00",
    "action": "BUY",
    "symbol": "000001.SZ",
    "shares": 100,
    "price": 10.5,
    "cost": 1050.0,
    "reason": "M12机会: volume_surge"
  }
]
```

#### 4. `scheduler_state.json` - 调度器状态

实时记录任务执行情况：

```json
{
  "running": true,
  "tasks": {
    "signal_pipeline": {
      "last_run": "2026-05-06T10:00:00",
      "run_count": 10,
      "error_count": 0,
      "last_status": "ok"
    }
  },
  "recent_runs": [...]
}
```

---

## ❓ 常见问题

### Q1: 调度器启动失败怎么办？

**检查步骤：**
1. 查看日志: `data/logs/scheduler.log`
2. 检查端口占用: 确保没有其他实例在运行
3. 清理缓存:
   ```bash
   # Windows
   Get-ChildItem -Path . -Include __pycache__ -Recurse | Remove-Item -Recurse -Force
   
   # Linux/Mac
   find . -type d -name "__pycache__" -exec rm -rf {} +
   ```

### Q2: M12 扫描没有发现机会？

**可能原因：**
1. **不在交易时段**: 检查当前时间是否在配置的时间窗口内
2. **股票池为空**: 检查 `data/stock_universe.json` 配置
3. **数据源问题**: 检查日志中是否有数据获取错误

**解决方法：**
```bash
# 手动触发扫描，查看详细输出
python -m m7_scheduler.cli run m12_a_share_scan -v
```

### Q3: 如何添加自定义信号？

**步骤：**
1. 创建文本文件，内容为你的观察或信息
2. 放入 `data/incoming/` 目录
3. 等待调度器自动处理（30分钟内）
4. 或手动触发: `python -m m7_scheduler.cli run signal_pipeline`

**示例文件** (`data/incoming/my_signal.txt`):
```
标题: 某公司发布重大利好公告
内容: 某公司今日宣布与行业龙头达成战略合作...
标的: 000001.SZ
```

### Q4: 如何查看模拟交易盈亏？

**方法1: 使用 Dashboard**
```bash
python -m pipeline.dashboard
# 访问 http://localhost:8000
```

**方法2: 直接查询数据库**
```python
from m9_paper_trader.paper_trader import PaperTrader

trader = PaperTrader()
positions = trader.get_positions()
for pos in positions:
    print(f"{pos['symbol']}: 盈亏 {pos['unrealized_pnl']}")
```

### Q5: 日志文件太大怎么办？

**自动清理：**
系统已配置日志轮转，旧日志会自动归档。

**手动清理：**
```bash
# 删除旧日志（保留最近7天）
find data/logs -name "*.log" -mtime +7 -delete
```

### Q6: 如何修改数据源配置？

编辑 `config/data_sources.yaml`:

```yaml
primary:
  a_share: futu      # 主数据源
  hk_share: futu
  us_share: futu

fallback:
  a_share: akshare   # 备用数据源
  hk_share: yfinance
  us_share: yfinance

scenarios:
  m9_price_update:   # M9 专用配置
    primary: futu
    fallback: akshare
```

---

## ⚙️ 高级配置

### 自定义任务调度

编辑 `m7_scheduler/scheduler.py`，添加自定义任务：

```python
def my_custom_task():
    """自定义任务"""
    print("执行自定义逻辑...")
    return {"status": "ok", "result": "完成"}

# 注册任务
scheduler.register_task(
    name="my_task",
    func=my_custom_task,
    interval_minutes=60,
    time_window=("09:00", "15:00"),
    description="我的自定义任务"
)
```

### 配置文件位置

| 配置项 | 文件路径 |
|--------|----------|
| 数据源配置 | `config/data_sources.yaml` |
| LLM 配置 | `config/llm_config.yaml` |
| 股票池配置 | `data/stock_universe.json` |
| 调度器配置 | 通过 CLI 参数传入 |

### 环境变量

```bash
# 禁用进度条（避免日志膨胀）
export TQDM_DISABLE=1

# 设置 Python 编码
export PYTHONIOENCODING=utf-8

# LLM API Key（如果使用）
export OPENAI_API_KEY=your_key_here
```

### 性能优化

**1. 调整扫描间隔**
```bash
# 降低扫描频率，减少资源消耗
python -m m7_scheduler.cli start --background \
  --signal-interval 60 \
  --price-interval 30
```

**2. 限制股票池大小**
编辑 `data/stock_universe.json`，减少 `intraday` 列表中的股票数量。

**3. 禁用不需要的任务**
```bash
# 禁用新闻采集
python -m m7_scheduler.cli start --background --no-news
```

---

## 📞 技术支持

### 日志位置
- 调度器日志: `data/logs/scheduler.log`
- 错误日志: 同一文件，包含 ERROR 级别信息

### 调试模式

```bash
# 前台运行，查看详细输出
python -m m7_scheduler.cli start

# 手动运行任务，启用详细日志
python -m m7_scheduler.cli run signal_pipeline -v
```

### 数据备份

**重要数据：**
- `data/portfolio.db` - 持仓数据
- `data/signals/signal_store.db` - 信号历史
- `data/paper_trade_log.json` - 交易记录

**备份命令：**
```bash
# 创建备份目录
mkdir -p backups/$(date +%Y%m%d)

# 复制关键数据
cp data/portfolio.db backups/$(date +%Y%m%d)/
cp data/signals/signal_store.db backups/$(date +%Y%m%d)/
cp data/paper_trade_log.json backups/$(date +%Y%m%d)/
```

---

## 📝 更新日志

### v2.0 (2026-05-06)
- ✅ M12 统一重构完成
- ✅ 修复 m0_core 导入错误
- ✅ 解决日志文件膨胀问题
- ✅ 新增一键启动脚本
- ✅ 完善用户文档

### v1.0 (2026-05-05)
- 初始版本发布
- 基础调度器功能
- M12 机会捕捉器
- 模拟交易系统

---

## 📄 许可证

本项目仅供学习和研究使用，不构成任何投资建议。

---

**祝交易顺利！** 🚀
