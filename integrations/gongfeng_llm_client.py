"""
integrations/gongfeng_llm_client.py — 工蜂AI直连客户端

直接调用 copilot-gateway，使用本地缓存的 OAuth access token。
绕开 localhost:3000 代理，直接访问工蜂AI后端。

⚠️  机器相关配置说明（见 docs/LLM_Config.md）

Token 缓存路径：
  Windows : %USERPROFILE%\.openclaw\agents\main\agent\auth-profiles.json
  macOS/Linux: ~/.openclaw/agents/main/agent/auth-profiles.json

API 端点：
  https://copilot.code.woa.com/server/openclaw/copilot-gateway/v1/chat/completions

必须携带的 Headers（缺任一个返回 400）：
  Authorization: Bearer <access>
  OAUTH-TOKEN: <access>
  X-Username: <username>
  DEVICE-ID: <deviceId>

注意：GET /models 返回 404 是正常的，不能用来做可用性检查。

用法：
    from integrations.gongfeng_llm_client import GongfengLLMClient
    client = GongfengLLMClient()
    reply = client.chat("分析这个信号", system="你是市场分析师")
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 工蜂 copilot-gateway 端点
GONGFENG_BASE_URL = "https://copilot.code.woa.com/server/openclaw/copilot-gateway/v1"
DEFAULT_MODEL = "gongfeng/gpt-5-4"

# 本地 OAuth token 缓存路径
AUTH_PROFILE_PATH = (
    Path.home() / ".openclaw" / "agents" / "main" / "agent" / "auth-profiles.json"
)


class GongfengLLMClient:
    """
    工蜂AI直连客户端。

    自动读取本地 OAuth access token，直接调用 copilot-gateway。
    兼容 M11 Agent 的 .chat(prompt, system) 接口。
    """

    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model
        self._token: str | None = None
        self._client = None

    def _load_profile(self) -> dict:
        """从本地 auth-profiles.json 读取完整 profile"""
        try:
            if not AUTH_PROFILE_PATH.exists():
                logger.warning("[GongfengLLM] auth-profiles.json 不存在")
                return {}
            data = json.loads(AUTH_PROFILE_PATH.read_text(encoding="utf-8"))
            profile = data.get("profiles", {}).get("gongfeng:default", {})
            if profile.get("access"):
                logger.debug(f"[GongfengLLM] 加载 profile: user={profile.get('username')}")
            return profile
        except Exception as e:
            logger.warning(f"[GongfengLLM] 读取 profile 失败: {e}")
        return {}

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            import httpx
            self._client = httpx.Client(timeout=30.0)
            return self._client
        except ImportError:
            logger.warning("[GongfengLLM] httpx 未安装，尝试 requests")
            try:
                import requests
                # 用 requests 适配器
                self._client = _RequestsAdapter()
                return self._client
            except ImportError:
                logger.error("[GongfengLLM] httpx 和 requests 均未安装")
                return None

    def _make_headers(self, profile: dict) -> dict:
        """构造工蜂API所需的完整 Headers"""
        token = profile.get("access", "")
        return {
            "Authorization": f"Bearer {token}",
            "OAUTH-TOKEN": token,
            "X-Username": profile.get("username", ""),
            "DEVICE-ID": profile.get("deviceId", ""),
            "Content-Type": "application/json",
            "X-Model-Name": "GPT-5.4",
        }

    def is_available(self) -> bool:
        """检查 token 和网络是否可用（用一个轻量 POST 测试）"""
        profile = self._load_profile()
        if not profile.get("access"):
            return False
        client = self._get_client()
        if client is None:
            return False
        try:
            # 用最小请求探活
            payload = {"model": self.model,
                       "messages": [{"role": "user", "content": "ping"}],
                       "max_tokens": 5}
            resp = client.post(
                f"{GONGFENG_BASE_URL}/chat/completions",
                json=payload,
                headers=self._make_headers(profile),
                timeout=5.0,
            )
            ok = resp.status_code == 200
            if ok:
                logger.info("[GongfengLLM] 工蜂AI可用")
            return ok
        except Exception as e:
            logger.debug(f"[GongfengLLM] 可用性检查失败: {e}")
            return False

    def chat(self, prompt: str, system: str = "") -> str:
        """
        调用工蜂AI，返回文本。
        兼容 M11 Agent 的 llm_client.chat(prompt, system) 接口。
        """
        profile = self._load_profile()
        if not profile.get("access"):
            raise RuntimeError("[GongfengLLM] 无可用 OAuth token")

        client = self._get_client()
        if client is None:
            raise RuntimeError("[GongfengLLM] HTTP 客户端初始化失败")

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 600,
            "temperature": 0.2,
        }

        try:
            resp = client.post(
                f"{GONGFENG_BASE_URL}/chat/completions",
                json=payload,
                headers=self._make_headers(profile),
                timeout=25.0,
            )
            if resp.status_code == 401:
                raise RuntimeError("[GongfengLLM] Token 已过期，需重新登录工蜂")
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            logger.debug(f"[GongfengLLM] 响应: {content[:80]}...")
            return content
        except Exception as e:
            logger.error(f"[GongfengLLM] 调用失败: {e}")
            raise

    def chat_completion(self, messages: list, **kwargs) -> str:
        """OpenAI 兼容接口（向后兼容）"""
        system = ""
        user_msgs = []
        for m in messages:
            if m.get("role") == "system":
                system = m["content"]
            else:
                user_msgs.append(m["content"])
        prompt = "\n".join(user_msgs)
        return self.chat(prompt, system=system)


class _RequestsAdapter:
    """requests 库适配器，模拟 httpx.Client 接口"""
    def __init__(self):
        import requests
        self._s = requests.Session()

    def get(self, url, headers=None, timeout=5.0, **kwargs):
        import requests
        return self._s.get(url, headers=headers, timeout=timeout)

    def post(self, url, json=None, headers=None, timeout=25.0, **kwargs):
        return self._s.post(url, json=json, headers=headers, timeout=timeout)


def make_gongfeng_client(model: str = DEFAULT_MODEL) -> Optional[GongfengLLMClient]:
    """工厂函数：创建工蜂AI客户端，不可用时返回 None"""
    client = GongfengLLMClient(model=model)
    return client  # 不做预检，让 Agent 在调用时处理失败
