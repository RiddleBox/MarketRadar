# MarketRadar — 二级市场机会发现系统

> **客观信号驱动，行动闭环管理**

MarketRadar 是一个基于客观信号（宏观/行业/资金/技术/政策/事件）的二级市场机会发现与行动管理系统。它从外部信息中提取结构化信号，判断是否构成可操作的市场机会，并生成包含止损/止盈/仓位管理的完整行动计划。

---

## 系统定位

```
外部信息（新闻/财报/宏观数据/政策文件）
         ↓
[M1] 信号解码 ──→ [M2] 信号存储
         ↓                ↑ 历史信号
[M3] 机会判断 ←───────────┘
         ↓
[M4] 行动设计
         ↓
[M5] 持仓管理 ←── 价格更新（手动/接口）
         ↓
[M6] 复盘归因
         
[M7] 回测引擎（历史验证，独立运行）
[M8] RAG 知识库（为 M3/M4 提供证据支撑）
```

**与 MarketSentinel（情绪面系统）的关系**：

MarketSentinel 是一个独立的多 Agent 情绪模拟系统，通过虚拟角色（散户/机构/外资/做市商）对同一信号产生不同情绪反应，模拟情绪面驱动的市场行为。MarketSentinel 的输出（`SentimentSignal`）通过标准接口注入 MarketRadar 的 M2 Signal Store，作为情绪维度信号参与机会判断。两个系统可独立运行，MarketRadar 不强依赖 MarketSentinel。

---

## 快速开始

### 安装依赖
```bash
pip install -r requirements.txt
```

### 配置 LLM API Key
当前推荐联调默认 provider 为 **DeepSeek**。

PowerShell 示例：
```powershell
$env:DEEPSEEK_API_KEY="<your-deepseek-key>"
```

### 运行联调主链路（当前推荐）
```powershell
pwsh -File .\run_dev_pipeline.ps1 -Provider deepseek
```

### 运行 Pipeline（分析一段文本）
```bash
python pipeline/run_pipeline.py --input data/incoming/sample.txt --market A_SHARE,HK
```

### 启动 Dashboard
```bash
streamlit run pipeline/dashboard.py
```

### 运行回测
```bash
python pipeline/run_backtest.py --start 2024-01-01 --end 2024-06-30 --market A_SHARE
```

### 运行测试
```bash
pytest tests/ -v
```

### 当前联调建议
- 默认联调 provider：`deepseek`
- `gongfeng` 已接入，但当前可能遇到 429 限流
- `xfyun` 可作为备用 provider
- 端到端主链路验证脚本：`test_pipeline.py`
- 统一联调入口脚本：`run_dev_pipeline.ps1`

---

## 模块说明

| 模块 | 目录 | 核心功能 |
|------|------|---------|
| M1 信号解码 | `m1_decoder/` | 从原始文本提取结构化 MarketSignal |
| M2 信号存储 | `m2_storage/` | 跨批次积累信号，支持时间范围检索 |
| M3 机会判断 | `m3_judgment/` | 信号组合 → 机会识别，空列表是合法输出 |
| M4 行动设计 | `m4_action/` | 机会 → 可执行行动计划（含止损/止盈） |
| M5 持仓管理 | `m5_position/` | 跟踪持仓，检查止损/止盈触发 |
| M6 复盘归因 | `m6_retrospective/` | 结构化复盘，区分运气与判断力 |
| M7 回测引擎 | `m7_backtester/` | 历史数据验证判断框架（前向隔离） |
| M8 知识库 | `m8_knowledge/` | RAG 证据支撑（估值框架/历史案例） |

每个模块均有独立的 `PRINCIPLES.md`——**这是最重要的文档**，定义了模块的存在意义和设计约束，实现必须围绕这些原则展开。

---

## 设计原则

1. **信号是一等公民**：所有机会必须有信号溯源，不允许无根据的机会输出
2. **市场标识前置**：每条信号必须标注影响市场（A_SHARE/HK/US/期货/期权），机会继承市场标识
3. **时间是核心参数**：信号携带 `event_time`（事件时间）和 `collected_time`（收集时间），回测严格按 `event_time` 前向隔离
4. **空列表是合法输出**：M3 不够信号时不强行输出机会，这是健康的系统行为
5. **止损比止盈更重要**：M4 的每个行动计划必须有具体止损条件
6. **回测验证框架，不优化参数**：M7 的目的是检验判断框架有效性，而非寻找最优参数

---

## 项目来源

MarketRadar 是从 [DesignAssistant](https://github.com/RiddleBox/DesignAssistant) 的工程经验中提炼的独立项目：
- 保留：pipeline 骨架、信号评分框架、Signal Store 三步结构（Step A/B/C）、LLM 客户端
- 重建：信号 taxonomy（适配二级市场）、机会判断框架（适配交易决策）、行动闭环（含持仓管理/止损）、回测引擎（二级市场独有）
- 新增：市场标识前置、时间范围参数化、MarketSentinel 接口预留
