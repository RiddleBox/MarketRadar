"""
integrations/llm_adapter.py — 统一 LLM 适配器

将项目中不同接口的 LLM Client 统一为 M11 Agent 所需的接口。

M11 BaseMarketAgent 期望：
    llm_client.chat(prompt: str, system: str) -> str

现有 Client：
    LLMClient（m1_decoder）：chat_completion(messages, module_name) -> str
    OpenClawLLMClient（integrations）：chat_completion(messages) -> str

使用方法：
    # DeepSeek（默认）
    client = make_llm_client("deepseek")

    # OpenClaw 工蜂AI
    client = make_llm_client("openclaw")

    # 接入 AgentNetwork
    net = AgentNetwork._default_a_share(llm_client=client, use_llm=True)
"""
from __future__ import annotations

import logging
from typing import Literal, Optional

logger = logging.getLogger(__name__)


class LLMAdapter:
    """
    通用 LLM 适配器。

    将任意 LLM Client 的接口统一为：
        .chat(prompt, system) -> str

    同时保留 .chat_completion(messages) 接口（向后兼容）。
    """

    def __init__(self, raw_client, provider_name: str = "unknown"):
        self._raw = raw_client
        self.provider_name = provider_name

    def chat(self, prompt: str, system: str = "") -> str:
        """
        M11 Agent 调用接口。

        优先级：
        1. raw_client.chat(prompt, system)          — 直接支持
        2. raw_client.chat_completion(messages)     — OpenAI 兼容
        3. raw_client.chat_completion(messages, module_name)  — LLMClient
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        # 尝试 .chat() 直接接口
        if hasattr(self._raw, "chat") and callable(self._raw.chat):
            try:
                return self._raw.chat(prompt=prompt, system=system)
            except TypeError:
                pass

        # 尝试 .chat_completion(messages, module_name)（LLMClient 风格）
        if hasattr(self._raw, "chat_completion"):
            try:
                return self._raw.chat_completion(messages, module_name="m11_agent_sim")
            except TypeError:
                return self._raw.chat_completion(messages)

        raise RuntimeError(f"[LLMAdapter] {self.provider_name} 不支持任何已知接口")

    def chat_completion(self, messages: list, **kwargs) -> str:
        """向后兼容接口"""
        if hasattr(self._raw, "chat_completion"):
            return self._raw.chat_completion(messages, **kwargs)
        raise RuntimeError(f"[LLMAdapter] {self.provider_name} 不支持 chat_completion")

    def is_available(self) -> bool:
        if hasattr(self._raw, "is_available"):
            return self._raw.is_available()
        return True  # 默认假设可用

    def __repr__(self) -> str:
        return f"LLMAdapter(provider={self.provider_name})"


def make_llm_client(
    provider: Literal["deepseek", "openclaw", "auto"] = "auto",
    fallback_to_rules: bool = True,
) -> Optional[LLMAdapter]:
    """
    工厂函数：创建适配后的 LLM Client

    Args:
        provider: "deepseek" / "openclaw" / "auto"（auto 优先用 openclaw，失败用 deepseek）
        fallback_to_rules: 所有 LLM 都不可用时返回 None（触发规则模式降级）

    Returns:
        LLMAdapter 或 None（触发规则模式）
    """
    if provider in ("openclaw", "auto"):
        try:
            from integrations.openclaw_market_brief import OpenClawLLMClient
            oc = OpenClawLLMClient()
            if oc.is_available():
                logger.info("[LLMAdapter] 使用 OpenClaw 工蜂AI 模型")
                return LLMAdapter(oc, provider_name="openclaw")
            else:
                logger.info("[LLMAdapter] OpenClaw Gateway 不可用")
        except Exception as e:
            logger.debug(f"[LLMAdapter] OpenClaw 初始化失败: {e}")

        if provider == "openclaw":
            if fallback_to_rules:
                logger.warning("[LLMAdapter] openclaw 不可用，降级到规则模式")
                return None
            raise RuntimeError("OpenClaw LLM 不可用")

    if provider in ("deepseek", "auto"):
        try:
            import sys
            from pathlib import Path
            ROOT = Path(__file__).parent.parent
            if str(ROOT) not in sys.path:
                sys.path.insert(0, str(ROOT))
            from m1_decoder.decoder import LLMClient
            ds = LLMClient()
            logger.info("[LLMAdapter] 使用 DeepSeek（via LLMClient）")
            return LLMAdapter(ds, provider_name="deepseek")
        except Exception as e:
            logger.warning(f"[LLMAdapter] DeepSeek 初始化失败: {e}")

    if fallback_to_rules:
        logger.warning("[LLMAdapter] 所有 LLM 不可用，使用规则模式")
        return None
    raise RuntimeError("所有 LLM 提供商均不可用")
