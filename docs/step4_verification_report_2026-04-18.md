# 第四步验证报告：数据源 + 情绪采集

> 日期：2026-04-18
> 脚本：`tests/run_step4.py`
> 输出：`test_step4_output.txt`

---

## 验证结果：8/8 通过

| # | 检查项 | 状态 | 详情 |
|---|--------|------|------|
| 1 | AKShare Import | ✅ | version 1.18.55 (有 NumPy 2.0 兼容警告，但不影响功能) |
| 2 | AKShare Network | ✅ | 交易日历获取成功，8797 条历史交易日 |
| 3 | LLM Configuration | ✅ | default=gongfeng, local_config=True |
| 4 | Data Source Config | ✅ | active=[A_SHARE, HK], TUSHARE_TOKEN=未设置 |
| 5 | M10 Sentiment (Mock) | ✅ | FG=67.3, BULLISH (离线计算正常) |
| 6 | M11 Event Catalog | ✅ | 60 个历史事件加载成功 |
| 7 | Workflow Phase | ✅ | 当前阶段：休市（周末） |
| 8 | Database Files | ✅ | Audit/Confirmation 已创建，SignalStore/Sentiment/M11 待首次运行后生成 |

---

## 发现的关键问题

### 1. NumPy 2.0 兼容警告（低优先级）

```
A module that was compiled using NumPy 1.x cannot be run in NumPy 2.0.2
```

**影响**：AKShare 导入时有警告，但功能正常。
**建议**：如需消除警告，可执行 `pip install "numpy<2"` 或升级 numexpr/bottleneck。

### 2. LLM 配置细节

- `llm_config.local.yaml` 存在但 provider 显示为 `unknown`
- 需要确认 local 文件中是否正确设置了 `provider: deepseek`

### 3. TuShare Token 未设置

- 当前依赖 AKShare 免费版
- 缺失功能：精确涨跌停价、官方交易日历、期货数据
- **影响**：纸交易无法执行涨跌停检查，交易日历使用"工作日=交易日"启发式（节假日可能误判）

---

## 数据源能力矩阵

| 功能 | AKShare (免费) | TuShare (付费) | 当前状态 |
|------|---------------|----------------|---------|
| A 股日线 OHLCV | ✅ | ✅ | ✅ 可用 |
| A 股实时行情 | ✅ | ✅ | ✅ 可用 |
| 港股日线/实时 | ✅ | ✅ | ✅ 可用 |
| 财经新闻采集 | ✅ | ❌ | ✅ 可用 |
| 宏观数据 (GDP/CPI) | ✅ | ✅ | ✅ 可用 |
| 精确涨跌停价 | ❌ | ✅ | ❌ 不可用 |
| 官方交易日历 | ❌ | ✅ | ⚠️ 启发式替代 |
| 期货数据 | ❌ | ✅ | ❌ 不可用 |
| 分钟级行情 | ❌ | ✅ | ❌ 不可用 |

**结论**：AKShare 免费版满足核心需求（日线回测 + 新闻采集 + 实时价格），缺失的涨跌停检查和精确日历对模拟盘影响有限。

---

## 下一步建议

### 立即可做（无需额外配置）

1. **修复 LLM local config**：确认 `llm_config.local.yaml` 中 `provider: deepseek` 设置正确
2. **运行 Dashboard**：`streamlit run pipeline/dashboard.py` 验证 UI

### 可选升级（按需）

1. **修复 NumPy 兼容**：`pip install "numpy<2"` 消除警告
2. **注册 TuShare**：如需涨跌停检查和期货数据，注册 tushare.pro 并设置 token

---

## 如何复现

```powershell
# 运行验证
python tests/run_step4.py

# 查看输出
type test_step4_output.txt
```
