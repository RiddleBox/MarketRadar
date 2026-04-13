"""
core/llm_client.py — 统一 LLM 调用客户端

支持多 provider（DeepSeek / Claude / OpenAI），使用 OpenAI-compatible API。
支持每个模块的独立配置覆盖（temperature、provider 等）。
内置重试逻辑、超时处理和详细错误日志。
"""

from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from openai import OpenAI, APITimeoutError, RateLimitError, APIError

logger = logging.getLogger(__name__)


def _resolve_env_vars(value: Any) -> Any:
    """
    递归替换字符串中的环境变量占位符。
    支持 ${VAR_NAME} 语法。
    """
    if isinstance(value, str):
        pattern = re.compile(r"\$\{(\w+)\}")
        def replacer(match: re.Match) -> str:
            var_name = match.group(1)
            env_val = os.environ.get(var_name)
            if env_val is None:
                logger.warning(f"Environment variable '{var_name}' not set")
                return match.group(0)  # 保留原始占位符，不报错
            return env_val
        return pattern.sub(replacer, value)
    elif isinstance(value, dict):
        return {k: _resolve_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_resolve_env_vars(item) for item in value]
    return value


class LLMClient:
    """
    统一 LLM 调用客户端。

    从 config/llm_config.yaml 加载配置，支持：
    - 多 provider（deepseek / claude / openai）
    - 模块级配置覆盖（不同模块用不同温度/provider）
    - 自动重试（timeout / rate_limit 错误）
    - 环境变量替换

    Usage:
        client = LLMClient()
        response = client.chat_completion(
            messages=[{"role": "user", "content": "你好"}],
            module_name="m1_decoder"
        )
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化 LLM 客户端。

        Args:
            config_path: llm_config.yaml 的路径。
                        默认自动查找项目根目录下的 config/llm_config.yaml
        """
        self._config = self._load_config(config_path)
        self._clients: Dict[str, OpenAI] = {}
        logger.info(f"LLMClient initialized with default provider: {self._config['default_provider']}")

    def _load_config(self, config_path: Optional[str]) -> dict:
        """加载并解析 LLM 配置文件"""
        if config_path is None:
            # 自动查找配置文件
            candidates = [
                Path(__file__).parent.parent / "config" / "llm_config.yaml",
                Path("config") / "llm_config.yaml",
                Path("llm_config.yaml"),
            ]
            for candidate in candidates:
                if candidate.exists():
                    config_path = str(candidate)
                    break
            else:
                raise FileNotFoundError(
                    "llm_config.yaml not found. Please create config/llm_config.yaml "
                    "or pass config_path explicitly."
                )

        with open(config_path, "r", encoding="utf-8") as f:
            raw_config = yaml.safe_load(f)

        # 解析环境变量
        return _resolve_env_vars(raw_config)

    def _get_provider_config(self, module_name: str) -> tuple[str, dict]:
        """
        获取指定模块的 provider 名称和配置。

        Returns:
            (provider_name, provider_config)
        """
        # 检查模块级覆盖
        overrides = self._config.get("module_overrides", {})
        module_override = overrides.get(module_name, {})

        # 确定使用的 provider
        provider_name = module_override.get("provider", self._config["default_provider"])

        # 获取 provider 基础配置
        providers = self._config.get("providers", {})
        if provider_name not in providers:
            raise ValueError(
                f"Provider '{provider_name}' not found in config. "
                f"Available providers: {list(providers.keys())}"
            )

        provider_config = dict(providers[provider_name])

        # 应用模块级覆盖（temperature 等）
        for key, value in module_override.items():
            if key != "provider":
                provider_config[key] = value

        return provider_name, provider_config

    def _get_or_create_client(self, provider_name: str, provider_config: dict) -> OpenAI:
        """获取或创建 OpenAI 客户端实例（按 provider 缓存）"""
        if provider_name not in self._clients:
            api_key = provider_config.get("api_key", "")
            base_url = provider_config.get("base_url")

            # 检查 API key 是否有效
            if not api_key or api_key.startswith("${"):
                logger.warning(
                    f"Provider '{provider_name}' API key may not be set correctly: {api_key!r}"
                )

            self._clients[provider_name] = OpenAI(
                api_key=api_key,
                base_url=base_url,
            )
            logger.debug(f"Created OpenAI client for provider '{provider_name}' at {base_url}")

        return self._clients[provider_name]

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        module_name: str = "default",
        **kwargs: Any,
    ) -> str:
        """
        发送 chat completion 请求，返回模型回复文本。

        Args:
            messages: 消息列表，格式 [{"role": "user/assistant/system", "content": "..."}]
            module_name: 模块名称，用于查找模块级配置覆盖。
                        例：'m1_decoder', 'm3_judgment', 'default'
            **kwargs: 额外参数，会覆盖配置文件中的值。
                     常用：temperature, max_tokens, response_format

        Returns:
            模型回复的文本内容

        Raises:
            RuntimeError: 重试次数耗尽后仍然失败
        """
        provider_name, provider_config = self._get_provider_config(module_name)
        client = self._get_or_create_client(provider_name, provider_config)

        model = provider_config.get("model", "gpt-4o")
        timeout = provider_config.get("timeout", 60)
        max_retries = provider_config.get("max_retries", 3)
        temperature = provider_config.get("temperature", 0.1)

        # 允许调用者覆盖任何参数
        request_params: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "timeout": timeout,
        }
        request_params.update(kwargs)

        last_exception: Optional[Exception] = None

        for attempt in range(1, max_retries + 1):
            try:
                logger.debug(
                    f"LLM request: provider={provider_name}, module={module_name}, "
                    f"attempt={attempt}/{max_retries}, model={model}"
                )

                response = client.chat.completions.create(**request_params)
                content = response.choices[0].message.content

                if content is None:
                    raise ValueError("LLM returned empty content")

                logger.debug(
                    f"LLM response received: {len(content)} chars, "
                    f"usage={response.usage}"
                )
                return content

            except APITimeoutError as e:
                last_exception = e
                wait_time = 2 ** attempt
                logger.warning(
                    f"Timeout on attempt {attempt}/{max_retries}. "
                    f"Waiting {wait_time}s before retry..."
                )
                if attempt < max_retries:
                    time.sleep(wait_time)

            except RateLimitError as e:
                last_exception = e
                # 速率限制：等待更长时间
                wait_time = 10 * attempt
                logger.warning(
                    f"Rate limit on attempt {attempt}/{max_retries}. "
                    f"Waiting {wait_time}s before retry..."
                )
                if attempt < max_retries:
                    time.sleep(wait_time)

            except APIError as e:
                last_exception = e
                logger.error(
                    f"API error on attempt {attempt}/{max_retries}: "
                    f"status={e.status_code}, message={e.message}"
                )
                # 4xx 客户端错误通常不可重试（除了 429）
                if e.status_code and 400 <= e.status_code < 500 and e.status_code != 429:
                    raise RuntimeError(
                        f"Non-retryable API error: {e.status_code} - {e.message}"
                    ) from e
                if attempt < max_retries:
                    time.sleep(2 ** attempt)

            except Exception as e:
                last_exception = e
                logger.error(f"Unexpected error on attempt {attempt}: {e}")
                if attempt < max_retries:
                    time.sleep(2)

        raise RuntimeError(
            f"LLM call failed after {max_retries} attempts. "
            f"Last error: {last_exception}"
        ) from last_exception

    def get_provider_info(self, module_name: str = "default") -> dict:
        """
        获取指定模块将使用的 provider 信息（脱敏）。
        用于日志和调试。
        """
        provider_name, config = self._get_provider_config(module_name)
        return {
            "provider": provider_name,
            "model": config.get("model"),
            "base_url": config.get("base_url"),
            "temperature": config.get("temperature"),
            "max_retries": config.get("max_retries"),
            "api_key_set": bool(config.get("api_key") and not config.get("api_key", "").startswith("${")),
        }


# 全局单例（懒加载）
_default_client: Optional[LLMClient] = None


def get_default_client() -> LLMClient:
    """
    获取全局默认 LLM 客户端单例。
    首次调用时初始化，后续复用同一实例。
    """
    global _default_client
    if _default_client is None:
        _default_client = LLMClient()
    return _default_client
