# LLM 接入配置指南

## 概述

MarketRadar 的 M11 AgentNetwork 支持两种 LLM 接入模式：

| 模式 | 方式 | 适用场景 |
|------|------|---------|
| **工蜂AI直连** | 读取 OpenClaw 本地 OAuth token | 腾讯内网机器（推荐）|
| **DeepSeek** | 环境变量 `DEEPSEEK_API_KEY` | 任意机器（通用备用）|
| **规则模式** | 无需 LLM | 离线/测试环境降级 |

---

## 方案一：工蜂AI直连（GongfengLLMClient）

> 适用于腾讯内网 + 已登录 OpenClaw 的机器

### 原理

OpenClaw 登录后会在本地缓存 OAuth token，`GongfengLLMClient` 自动读取并直接
调用工蜂 copilot-gateway，无需手动配置任何 API Key。

### Token 缓存路径

| 操作系统 | 路径 |
|---------|------|
| Windows | `%USERPROFILE%\.openclaw\agents\main\agent\auth-profiles.json` |
| macOS/Linux | `~/.openclaw/agents/main/agent/auth-profiles.json` |

### 所需字段（从 auth-profiles.json 读取）

```json
{
  "profiles": {
    "gongfeng:default": {
      "access":   "<OAuth token>",   // → OAUTH-TOKEN & Authorization Bearer
      "username": "lidaldzhou",       // → X-Username header
      "deviceId": "01ec02bc-..."      // → DEVICE-ID header
    }
  }
}
```

### API 端点

```
POST https://copilot.code.woa.com/server/openclaw/copilot-gateway/v1/chat/completions
```

### 必须携带的 Headers（缺任一个返回 400，无详细错误提示）

```
Authorization: Bearer <access>
OAUTH-TOKEN: <access>
X-Username: <username>
DEVICE-ID: <deviceId>
Content-Type: application/json
X-Model-Name: GPT-5.4
```

> ⚠️ **GET /models 返回 404 是正常的**，不能用来做可用性检查。
> 用一次小 POST `/chat/completions` 探活，或直接忽略（失败自动降级）。

### 使用方式

```python
from integrations.gongfeng_llm_client import GongfengLLMClient
from integrations.llm_adapter import LLMAdapter
from m11_agent_sim.agent_network import AgentNetwork

llm = LLMAdapter(GongfengLLMClient(), provider_name="gongfeng")
net = AgentNetwork.from_config_file("a_share", llm_client=llm, use_llm=True)
```

### 换机器时检查清单

- [ ] `auth-profiles.json` 存在且 `gongfeng:default` 有效
- [ ] 网络可访问 `copilot.code.woa.com`（需要 IOA 认证 / 内网）
- [ ] Python 已安装 `httpx`（`pip install httpx`），或退回 `requests`
- [ ] OpenClaw 已登录（token 有效期很长，但换机器需重新登录生成新 token）

---

## 方案二：DeepSeek（通用备用）

任何机器均可使用，无需 OpenClaw。

```bash
# .env 文件 或 直接设置环境变量
DEEPSEEK_API_KEY=sk-xxxxxxxx
```

```python
from integrations.llm_adapter import make_llm_client
llm = make_llm_client("deepseek")  # 自动读取环境变量
```

---

## 方案三：规则模式（离线降级）

不传 `llm_client` 或 LLM 不可用时自动降级，不影响系统正常运行：

```python
net = AgentNetwork.from_config_file("a_share")  # use_llm=False，规则模式
```

规则模式下 Agent 方向准确率约 85%（历史回测），LLM 模式 94.4%。

---

## ablation_study.py 的 LLM 优先级

`backtest/ablation_study.py` 的 `_get_llm_client()` 按以下顺序尝试：

1. `GongfengLLMClient`（工蜂AI直连）
2. `make_llm_client("auto")`（读取环境变量，依次尝试 DeepSeek / OpenClaw Gateway）
3. `None`（规则模式）

---

## OpenClaw Gateway 模式（暂不可用）

OpenClaw Gateway 在本地运行时会暴露 `http://localhost:3000/v1`（OpenAI 兼容格式），
`OpenClawLLMClient`（`integrations/openclaw_market_brief.py`）依赖此端点。

当前云桌面机器 Gateway 未运行，此模式不可用。如果 Gateway 启动：
- 端口：`3000`（默认）或 `23001`
- 所需 Header 待验证（可能与直连方式不同）

---

## 模型配置

当前项目修复周期统一使用 `gongfeng/gpt-5-4`，默认链路应优先走工蜂 OAuth 直连，不再把 Claude 设为主链路默认值。

```python
client = GongfengLLMClient(model="gongfeng/gpt-5-4")  # 默认
```

推荐顺序：
- `gongfeng/gpt-5-4`（主链路，当前唯一推荐默认模型）
- `deepseek-v3-2`（仅备用）

如果某个脚本仍写死 Claude 名称，应优先修正该脚本，而不是继续沿用 Claude。
