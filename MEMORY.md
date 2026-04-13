# MarketRadar — 项目记忆 & 环境注意事项

## 项目进展（截至 2026-04-13）

### 已完成模块

| 模块 | 状态 | 说明 |
|------|------|------|
| M10 情绪面分析 | ✅ | FG指数+北向+ADR综合评分 |
| M11 AgentNetwork | ✅ | 5-Agent 串行拓扑，规则+LLM双模式 |
| M11 LLM接入 | ✅ | 工蜂AI直连（见下方配置说明） |
| 历史种子数据 | ✅ | 20个典型A股机会（2018~2025） |
| 历史回测主程序 | ✅ | 胜率85%，高强度案例100% |
| 消融实验 | ✅ | 5策略×hard/soft，LLM模式验证 |

### 消融实验关键结果（LLM模式，2026-04-13）

- **Baseline**：胜率 85%，均盈亏 +1.23%
- **+Sentiment**：胜率 100%，均盈亏 +8.26%（过滤率40%）
- **+Agent(LLM)**：胜率 94.4%，均盈亏 +7.24%（过滤率25%）
- **Full策略**：胜率 100%，均盈亏 +9.81%（过滤率45%）
- 结论：情绪面是最强单模块；LLM Agent 显著优于规则模式（+10pp胜率）

### 最新 commits
```
4872a6d feat: 工蜂AI直连LLM客户端; 消融实验LLM模式完成
63b99cd fix: 修复ablation Agent输入构造(SentimentContext+SignalContext)
6147543 feat: 消融实验模块(5策略×hard/soft)
05a7482 feat: 20个历史机会种子数据+历史回测主程序
d03d3c2 feat: OpenClaw LLM入口 + M3情绪共振 + LLM适配器
8e2ed3b feat(m11): MultiAgentSim 5-agent sequential network
```

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

#### OpenClaw Gateway 状态（当前机器）

- Gateway **未在当前机器上运行**（`localhost:3000` 和 `localhost:23001` 均不通）
- LLM 调用走直连方案（`gongfeng_llm_client.py`），不依赖 Gateway
- 如果 Gateway 上线，`llm_adapter.py` 的 `make_llm_client("openclaw")` 走 `localhost:3000/v1`
  - 需要的 Header 可能不同，待验证

#### DeepSeek（备用方案）

```bash
# 环境变量方式（任何机器都适用）
$env:DEEPSEEK_API_KEY = "sk-xxx"
python backtest/ablation_study.py
```

`llm_adapter.py` 的 `make_llm_client("deepseek")` 会自动读取环境变量。

---

## 下一步计划（待定）

- [ ] 港股回测（hk 市场配置）
- [ ] M12 实时信号接入
- [ ] 前端可视化（消融实验图表）
- [ ] Agent Prompt 优化（特别是 hist_009 NEUTRAL 误判）
