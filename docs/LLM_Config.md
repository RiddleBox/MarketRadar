# LLM 接入配置指南

## 概述

MarketRadar 的当前修复周期统一以 **gongfeng/gpt-5-4** 为唯一推荐主链路。

> 2026-04-14 runtime note: 当前已确认默认 provider 与模块级覆盖都解析到 `gongfeng/gpt-5-4`，未观察到 Claude 被实际选中。当前主阻塞点不是 provider 路由，而是 M3 Step B 在真实调用中偶发返回脏/截断 JSON；相关失败会自动落到 `docs/anchors/m3-stepb-parse-failure-*.md` 供排障。

| 模式 | 方式 | 适用场景 |
|------|------|---------|
| **工蜂AI主链路** | `core.LLMClient` + 本地 OpenClaw OAuth token | 腾讯内网机器（当前默认/推荐）|
| **OpenClaw Gateway** | `http://localhost:3000/v1` OpenAI-compatible | 本地 Gateway 已启动时的次选链路 |
| **DeepSeek** | 环境变量 `DEEPSEEK_API_KEY` | 仅在主链路不可用时备用 |
| **规则模式** | 无需 LLM | 离线/测试环境降级 |

---

## 方案一：工蜂AI主链路（推荐，当前默认）

优先建议直接使用 `core/llm_client.py` + `config/llm_config.yaml`，因为这是 M1/M3/M4 主流程真正使用的统一入口。

### 当前默认解析

```yaml
default_provider: gongfeng
providers:
  gongfeng:
    model: gongfeng/gpt-5-4
    auth_type: gongfeng_oauth
```

可用以下命令核对实际解析：

```powershell
python .\scripts\inspect_llm_runtime.py
python .\scripts\assert_gongfeng_runtime.py
```

如果输出中的 `default` / `m1_decoder` / `m3_judgment` / `m4_action` 仍指向 `gongfeng / gongfeng/gpt-5-4`，且断言脚本返回 `RUNTIME_ASSERT_OK`，说明主链路解析正确。

### 兼容封装：GongfengLLMClient

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

## 方案二：OpenClaw Gateway（次选）

当本机已启动 OpenClaw Gateway，且 `http://localhost:3000/v1` 可访问时，可通过 `OpenClawLLMClient` 走本地兼容入口。

注意：这不是当前默认主链路，当前默认仍应优先使用工蜂 OAuth 直连。

## 方案三：DeepSeek（通用备用）

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

## 方案四：规则模式（离线降级）

不传 `llm_client` 或 LLM 不可用时自动降级，不影响系统正常运行：

```python
net = AgentNetwork.from_config_file("a_share")  # use_llm=False，规则模式
```

规则模式下 Agent 方向准确率约 85%（历史回测），LLM 模式 94.4%。

---

## make_llm_client() 的当前优先级

`integrations/llm_adapter.py` 当前约定：

1. `make_llm_client("gongfeng")`：强制走 `core.LLMClient` 的工蜂 OAuth 主链路
2. `make_llm_client("openclaw")`：强制走 localhost Gateway
3. `make_llm_client("deepseek")`：强制走 DeepSeek 备用链路
4. `make_llm_client("auto")`：依次尝试 `gongfeng -> openclaw -> deepseek -> 规则模式`

这次修复的目标是：**不再让任何默认链路优先落到 Claude。**

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
