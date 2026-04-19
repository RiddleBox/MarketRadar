# MarketRadar — 项目记忆 & 环境注意事项

## 项目进展（截至 2026-04-18）

### 当前阶段：Iteration 11 进行中（M11 Agent 优化 + LLM 校准）

Iteration 1~10 全部完成。253+ tests passed。
M10 准入主链（并行输入层），M11 不准入（校准未达标：LLM 方向命中率 40% < 70% 阈值）。
盘前/盘中/盘后工作流 + 人工确认机制 + 审计日志 + Dashboard 6 tab 已上线。
项目从"研究原型"升级为"交易研究助手"。

### M11 LLM 校准进展（2026-04-19 Iter 11.5 — 信号精度修复）

| 运行 | 模式 | 阈值 | 方向命中率 | 选择性准确率 | 跳过率 |
|------|------|------|-----------|------------|--------|
| Iter 10 原始 | Rule+synthetic | 2% | 21.67% | — | — |
| Iter 10 原始 | LLM+synthetic | 2% | 36.67% | — | — |
| Iter 11 优化 | Rule+synthetic | 3% | 48.33% | — | — |
| Iter 11.4 修复 | LLM+synthetic | 3% | 40.00% | — | — |
| **Iter 11.5** | **Rule+decorrelated+0.50gate** | **3%** | **61.7%** | **48.0%** | **58.3%** |

Iter 11.5 核心改进（根因：信号精度）：
1. **SentimentProvider 可配置架构**：`sentiment_provider.py` — 3种数据源（synthetic/decorrelated/m10），消除循环信号
2. **去相关情绪**：FG 不再是 price_5d_chg*200+50，改用 signal_dir + 真实历史硬编码 + NEUTRALE化弱信号
3. **FundamentalAgent 反杀修复**：均值回归仅在 FG<25 极度恐惧时才给 bullish bias，不再反杀3-8%持续下跌
4. **置信度门控**：min_confidence 参数，低置信→NEUTRAL+no_trade，为胜率而交易
5. **选择性准确率指标**：selective_accuracy/skip_rate，量化"不交易"策略

教训：95%+ 的情绪数据是价格循环变换 → FundamentalAgent 用 FG 做"逆向判断"本质是自我抵消 → BEARISH命中率仅10%

### 已完成里程碑

| 里程碑 | 完成时间 | 说明 |
|--------|---------|------|
| Iteration 1: 测试基础设施修复 | 2026-04-17 | 9 个 WIP 测试→正式 pytest + M2/M5/M8 补充 + 根目录清理 + 119 passed |
| Iteration 2: 主链稳态收敛 | 2026-04-17 | llm_config.local.yaml + DeepSeek 接入 + smoke test + fallback 可观测性 |
| Iteration 3: M5/M6 闭环联调 | 2026-04-17 | ActionPlan direction/market + position_bridge + M6 timedelta/add_document 修复 + M1→M6 全闭环 |
| Iteration 4: 回测与数据层增强 | 2026-04-17 | FeeModel手续费/滑点 + by_signal_type丰富化 + by_direction + csv_cache真实化 + PriceLoader弃用 |
| Iteration 5: M3 评分框架完善 | 2026-04-17 | 评分维度定义+prompt增强 + _calibrate_priority() + _validate_invalidation_conditions() + 9+5 测试 |
| Iteration 6: M4 参数化行动设计 | 2026-04-17 | compute_kelly_position + compute_position_from_risk_budget + _build_action_plan参数化集成 + 品类模板差异化验证 + 19 测试 |
| Iteration 7A: 模拟盘核心增强 | 2026-04-17 | FeeModel共享(core/) + MarketRules(T+1/涨跌停/手数) + OrderStatus(4状态) + RiskMonitor + M6回调 + open_from_plan修复 + TradeLog + 37 测试 |
| Iteration 7B: 数据源+期货+资金曲线 | 2026-04-17 | TushareFeed(涨跌停/交易日历/分钟线) + CompositeFeed(fallback链) + EquityCurveTracker + 期货合约规格(IF/IC/IM/保证金) + open_futures() + 22 测试 |

### 消融实验关键结果（LLM模式，2026-04-13）

- **Baseline**：胜率 85%，均盈亏 +1.23%
- **+Sentiment**：胜率 100%，均盈亏 +8.26%（过滤率40%）
- **+Agent(LLM)**：胜率 94.4%，均盈亏 +7.24%（过滤率25%）
- **Full策略**：胜率 100%，均盈亏 +9.81%（过滤率45%）
- 结论：情绪面是最强单模块；LLM Agent 显著优于规则模式（+10pp胜率）

---

## 当前阻塞项

| # | 问题 | 优先级 |
|---|------|--------|
| 1 | M3 Step B JSON 解析偶发失败（DeepSeek下已大幅改善） | 中 |
| 2 | 全量测试需分批运行（pytest 超时） | 低 |
| 3 | M3 历史上下文增强（M2相似信号检索）未实现 | 中 |
| 4 | M4→M7 参数共享验证未实现 | 中 |
| 5 | M9 与 Dashboard/Scheduler 的接口适配7A改动 | ✅ 已解决 |
| 6 | TuShare token 配置（需用户注册+充值积分） | 中 |
| 7 | Prop Firm Dashboard 仪表盘 | ✅ 已解决（Dashboard 6 tab 已上线） |

---

## ⚠️ 环境配置注意事项（机器相关，不同机器需重确认）

### 当前机器：Windows Server（云桌面）

#### 工蜂AI LLM 直连配置

文件：`integrations/gongfeng_llm_client.py`

**认证方式**：读取 OpenClaw 本地 OAuth token 缓存（无需手动配置 API Key）

```
auth-profiles.json 路径：
  %USERPROFILE%\.openclaw\agents\main\agent\auth-profiles.json

所需字段：
  profiles["gongfeng:default"]["access"]   → Bearer token（即 OAUTH-TOKEN）
  profiles["gongfeng:default"]["username"] → X-Username header
  profiles["gongfeng:default"]["deviceId"] → DEVICE-ID header
```

**API 端点**：
```
https://copilot.code.woa.com/server/openclaw/copilot-gateway/v1/chat/completions
```

**必须携带的 Headers**（缺任一个都会 400）：
```
Authorization: Bearer <access_token>
OAUTH-TOKEN: <access_token>
X-Username: <username>
DEVICE-ID: <deviceId>
Content-Type: application/json
X-Model-Name: Claude Sonnet 4.6
```

**注意**：`GET /models` 返回 404，但 `POST /chat/completions` 正常工作。不要用 GET /models 做可用性检查。

#### 其他机器迁移清单

换机器时需要重新确认：
1. `auth-profiles.json` 路径是否相同（Windows vs Mac/Linux 路径不同）
2. token 是否有效（token 有效期至 2036 年，理论上长期有效）
3. 网络是否可访问 `copilot.code.woa.com`（需要 IOA 认证/内网）
4. Python 依赖：`httpx` 或 `requests` 二选一（`httpx` 优先）

#### DeepSeek（备用方案）

```bash
# 环境变量方式（任何机器都适用）
$env:DEEPSEEK_API_KEY = "sk-xxx"
python backtest/ablation_study.py
```

`llm_adapter.py` 的 `make_llm_client("deepseek")` 会自动读取环境变量。

---

## 迭代计划

详见：[docs/MarketRadar_Iteration_Plan_v2.md](docs/MarketRadar_Iteration_Plan_v2.md)

已完成：Iteration 1 / 2 / 3 / 4 / 5 / 6 / 7 / 8 / 9
当前状态：**所有迭代计划已完成**

## LLM 配置

- 默认 provider: deepseek（通过 `config/llm_config.local.yaml` 覆盖）
- 本地配置不入 Git（`.gitignore` 已包含）
- LLMClient 自动合并 `llm_config.yaml` + `llm_config.local.yaml`
- 密钥在 local 文件中，env var 为备用路径
