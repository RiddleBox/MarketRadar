# MarketRadar — 二级市场机会发现系统

> **推理型判断 · 信号驱动 · 行动闭环**

MarketRadar 是一个基于**推理引擎**的二级市场机会发现与行动管理系统。它不是"看到降准公告才判断"的反应型系统，而是通过**因果链推理**和**历史案例检索**，提前识别前置信号组合，预测未来事件概率，实现"提前14天预测降准概率80%"的推理型判断。

---

## 核心特性

### 🎯 推理型判断（不是反应型）
- **反应型**：看到降准公告才判断 → 所有人都看到了，无 alpha
- **推理型**：识别"央行讲话+财政发债+经济数据差"3个线索 → 推断降准概率80%，提前14天布局

### 🧠 因果图谱 + 历史案例
- **因果图谱**：记录"信号组合 → 未来事件"的因果关系（概率+时间窗口）
- **历史案例库**：从2020-2024历史数据中学习，案例检索支撑判断
- **初始数据**：10个货币政策因果模式，可扩展到50+（行业/个股/技术/资金）

### 🤖 端到端自动化
- **盘前（09:00）**：采集隔夜信号 → 解码 → 推理 → 生成今日机会列表
- **盘中（10:00/14:00）**：更新价格 → 检查止损止盈
- **盘后（15:30）**：复盘归因 → 更新知识库

### ✅ 验证结果
- **回测数据**：4个2023-2024降准/降息案例
- **事件预测准确率**：100%（4/4）
- **时间窗口准确率**：75%（3/4）
- **测试覆盖**：253+ tests passed

---

## 系统架构

```
外部信息（新闻/公告/研报/市场数据）
         ↓
[M0] 收集器 ──→ [M1] 信号解码 ──→ [M2] 信号存储
                      ↓                ↓
                  LLM提取          因果图谱
                   信号            历史案例
                                      ↓
                              [M3] 推理引擎
                                   ↓
                            因果链推理 + 案例检索
                                   ↓
                              机会判断（5个核心问题）
                                   ↓
[M4] 行动设计 ──→ [M5] 持仓管理 ──→ [M6] 复盘归因
     ↓                 ↓                  ↓
  仓位计算          止损止盈            知识沉淀
  Kelly/Risk        模拟盘              M8知识库

支撑层：M7调度器 | M8知识库 | M9模拟盘 | M10情绪感知
验证层：M11 Agent模拟 | 回测引擎 | 253+ 测试
```

---

## 10分钟快速开始

### 1. 克隆项目
```bash
git clone https://github.com/RiddleBox/MarketRadar.git
cd MarketRadar
```

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 配置环境变量
```bash
cp .env.example .env
nano .env  # 填入 OPENAI_API_KEY
```

### 4. 初始化因果图谱
```bash
mkdir -p data/incoming logs
python scripts/init_causal_graph.py
```

### 5. 运行盘前流程
```bash
python run_daily_pipeline.py --mode premarket
```

**预期输出**：
```
步骤 1/5: M0 采集隔夜信号
  ✓ 抓取到 15 条原始数据
  ✓ 去重后剩余 12 条

步骤 2/5: M10 情绪面快照
  ✓ 恐贪指数: 45
  ✓ 北向资金: +12.5亿

步骤 3/5: M1 信号解码
  ✓ 总计提取 8 条信号

步骤 4/5: M2 信号存储
  ✓ 保存 8 条信号（去重后）

步骤 5/5: M3 机会判断（推理引擎）
  ✓ 识别机会: 2 个

┌─────────────────────────────────────────────────────────┐
│                      今日机会列表                        │
├──────────┬────────┬─────────────────────┬──────────────┤
│ 优先级   │ 市场   │ 机会摘要            │ 推理事件     │
├──────────┼────────┼─────────────────────┼──────────────┤
│ POSITION │ A_SHARE│ 央行降准概率80%...  │ 2个预测事件  │
│ WATCHLIST│ A_SHARE│ 北向资金持续流入... │ 1个预测事件  │
└──────────┴────────┴─────────────────────┴──────────────┘

⚠️  请人工审核机会列表，决定是否执行
   查看详情: python pipeline/dashboard.py
```

### 6. 配置定时任务（可选）
```bash
# Linux/macOS
crontab -e
# 添加：0 9 * * 1-5 cd /path/to/MarketRadar && python run_daily_pipeline.py --mode premarket

# Windows：使用任务计划程序
# 详见：docs/定时任务配置指南.md
```

**完整指南**：[docs/快速开始指南.md](docs/快速开始指南.md)

---

## 文档索引

| 文档 | 说明 |
|------|------|
| [快速开始指南](docs/快速开始指南.md) | 10分钟从零到自动生成机会列表 |
| [实用性差距分析](docs/实用性差距分析.md) | 从研究原型到日常工具的路线图 |
| [定时任务配置指南](docs/定时任务配置指南.md) | crontab/systemd/Windows任务计划程序配置 |
| [可行性验证结果](docs/feasibility_validation_results.md) | 推理引擎验证报告（100%准确率） |
| [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) | 项目状态总览 + 模块文档索引 |

---

## 核心模块

| 模块 | 状态 | 说明 |
|------|------|------|
| M0 收集器 | ✅ | 4个数据源（RSS/新闻/公告/研报） |
| M1 信号解码 | ✅ | LLM提取"已发生的事实变化" |
| M2 信号存储 | ✅ | SQLite + 因果图谱 + 历史案例 |
| M3 机会判断 | ✅ | 推理引擎（因果链推理 + 案例检索） |
| M4 行动设计 | ✅ | Kelly/RiskBudget仓位计算 |
| M5 持仓管理 | ✅ | 止损止盈 + 模拟盘 |
| M6 复盘归因 | ✅ | 结构化归因 + 知识沉淀 |
| M7 调度器 | ✅ | 盘前/盘中/盘后工作流 |
| M8 知识库 | ✅ | 分析框架 + 行业知识 |
| M9 模拟盘 | ✅ | Paper Trading（已验证） |
| M10 情绪感知 | ✅ | FG指数 + 北向资金 |
| M11 Agent模拟 | ✅ | 5个agent串行拓扑 |

---

## 推理引擎示例

### 输入：3个前置信号
```
信号1: 央行行长讲话"适时降准"（2024-09-20）
信号2: 财政部提前发债（2024-09-18）
信号3: 8月CPI 0.6%，通缩压力（2024-09-10）
```

### M3推理过程
1. **因果模式匹配**：查询M2因果图谱
   - 匹配到模式：`pattern_rrr_cut_001`
   - 前置信号：政策表态 + 经济数据差
   - 后续事件：央行降准
   - 历史概率：80%
   - 时间窗口：14天内

2. **历史案例检索**：查询M2案例库
   - 相似案例：2024-02-05降准、2023-09-15降准
   - 共同特征：政策表态 + 通缩压力
   - 演化过程：信号出现后12-14天落地
   - 市场反应：+1.5% ~ +3.2%

3. **推理输出**：
   ```python
   InferredEvent(
       event_description="央行降准",
       probability=0.80,
       time_window="14天内",
       reasoning="三个前置信号指向宽松政策，历史上类似组合后2周内降准概率80%",
       supporting_pattern_ids=["pattern_rrr_cut_001"],
       supporting_cases=["case_2024_02_05", "case_2023_09_15"]
   )
   ```

4. **机会判断**：
   - 机会类型：政策驱动型
   - 优先级：POSITION（可建仓）
   - 时间窗口：2周内
   - 风险：如果14天内未落地，概率显著下降

### 实际结果
- **预测日期**：2024-09-20
- **实际公告**：2024-09-24（提前4天预测）
- **市场反应**：+2.5%

---

## 使用场景

### 场景1：每日盘前机会发现
```bash
# 每天早上9点自动运行
python run_daily_pipeline.py --mode premarket

# 输出：今日机会列表（含推理结果）
# 人工审核后决定是否执行
```

### 场景2：回测验证策略
```bash
# 回测2023-2024历史数据
python pipeline/run_backtest.py --start 2023-01-01 --end 2024-12-31

# 验证推理引擎准确率
python scripts/validate_inference_accuracy.py
```

### 场景3：模拟盘测试
```bash
# 运行模拟盘
python run_paper_trading_demo.py

# 测试止损/止盈逻辑
```

### 场景4：Dashboard查看
```bash
# 启动Dashboard
python pipeline/dashboard.py

# 浏览器打开 http://localhost:8050
# 查看：信号/机会/持仓/复盘/知识/审计
```

---

## 常见问题

### Q: 推理引擎准确率如何？
A: 回测4个2023-2024案例，事件预测准确率100%，时间窗口准确率75%。详见 [docs/feasibility_validation_results.md](docs/feasibility_validation_results.md)

### Q: 需要实时数据吗？
A: 不强制。可用AKShare（3-5分钟延迟，免费）。如需实时数据，可接入iTick/AllTick（需API Key）。

### Q: 支持本地模型吗？
A: 支持。可用Ollama/LM Studio替代OpenAI API。详见 [docs/快速开始指南.md](docs/快速开始指南.md)

### Q: 如何扩充因果图谱？
A: 当前10个货币政策模式。可手动添加或从历史数据自动提取。目标50+模式。详见 [docs/实用性差距分析.md](docs/实用性差距分析.md)

---

## 技术栈

- **语言**：Python 3.9+
- **LLM**：OpenAI API / Ollama / LM Studio
- **数据库**：SQLite
- **数据源**：AKShare / YFinance / iTick / AllTick
- **可视化**：Dash / Plotly
- **测试**：pytest（253+ tests）

---

## 路线图

### Phase 1：最小可用版本（已完成）
- ✅ M0→M6判断链
- ✅ M3推理引擎（因果链推理 + 案例检索）
- ✅ M9模拟盘验证
- ✅ 端到端自动化脚本

### Phase 2：扩展覆盖面（进行中）
- 🔄 扩充因果图谱（50+模式）
- 🔄 构建历史案例库（100+案例）
- 🔄 扩充M0数据源（政策文件/财报数据）
- 🔄 修复实时数据源（iTick/AllTick）

### Phase 3：智能化增强（规划中）
- ⏳ Dashboard实时推送 + 告警
- ⏳ M6复盘自动更新因果图谱
- ⏳ M11 Agent模拟准入主链
- ⏳ 策略参数自动优化

---

## 贡献指南

欢迎贡献！特别是：
- 扩充因果图谱（行业/个股/技术面模式）
- 添加历史案例（2020-2024成功/失败案例）
- 扩展数据源（社交媒体/政策文件/财报）
- 改进推理引擎（更精准的概率校准）

---

## 许可证

MIT License

---

## 联系方式

- **GitHub Issues**：https://github.com/RiddleBox/MarketRadar/issues
- **文档**：[docs/](docs/)

---

**MarketRadar** — 从"看到降准公告才判断"到"提前14天预测降准概率80%"
```powershell
python .\scripts\inspect_llm_runtime.py
```

只有当工蜂直连不可用时，才临时使用 OpenAI-compatible / 讯飞 / DeepSeek 作为备用；不要再把 Claude 作为主链路默认值。

### 检查实际运行时 LLM 路由
```powershell
python .\scripts\inspect_llm_runtime.py
```

### 运行联调主链路（当前推荐）
```powershell
pwsh -File .\run_dev_pipeline.ps1 -Provider gongfeng
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
先确认 pytest 已安装：
```bash
python -m pytest
```

当前建议的联调验收顺序：
```powershell
python .\scripts\assert_gongfeng_runtime.py
python -m pytest tests/test_schemas.py tests/test_m1.py tests/test_ingest.py -q
python test_pipeline.py
```

如需先确认运行时没有悄悄偏航到其他 provider：
```powershell
python .\scripts\assert_gongfeng_runtime.py
```

### 当前联调建议
- 默认配置 provider：`gongfeng`
- 默认模型：`gongfeng/gpt-5-4`
- `xfyun` / `deepseek` / `openai-compatible` 仅作为临时兼容或排障通道
- 端到端主链路验证脚本：`test_pipeline.py`
- 运行时解析检查脚本：`scripts/inspect_llm_runtime.py`
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
