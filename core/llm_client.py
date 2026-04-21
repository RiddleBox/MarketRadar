"""
core/llm_client.py — 统一 LLM 调用客户端

支持多 provider（工蜂AI / DeepSeek / Claude / OpenAI）。
工蜂AI使用 gongfeng_oauth 认证，自动读取本地 OpenClaw token，无需 API Key。
其他 provider 使用 OpenAI-compatible API + env var API Key。

配置文件：config/llm_config.yaml
详细说明见 docs/LLM_Config.md
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from openai import OpenAI, APITimeoutError, RateLimitError, APIError

logger = logging.getLogger(__name__)


# ───────────────────────────────────────────────────────────────────
class GongfengOAuthClient:
    """
    工蜂AI 直连客户端。

    自动读取本地 OpenClaw OAuth token，无需手动配置。
    必须携带 3 个自定义 Header：OAUTH-TOKEN / X-Username / DEVICE-ID。
    """

    def __init__(self, config: dict):
        self._config = config
        self._profile: Optional[dict] = None
        self._http = None

    def _load_profile(self) -> dict:
        """load OAuth profile from local OpenClaw cache"""
        if self._profile is not None:
            return self._profile
        raw_path = self._config.get(
            "auth_profile_path",
            "~/.openclaw/agents/main/agent/auth-profiles.json",
        )
        p = Path(raw_path).expanduser()
        # Windows 尝试替换路径
        if not p.exists() and os.name == "nt":
            p = Path(os.environ.get("USERPROFILE", "~")) / ".openclaw" / "agents" / "main" / "agent" / "auth-profiles.json"
        if not p.exists():
            raise RuntimeError(
                f"[GongfengOAuth] auth-profiles.json 不存在: {p}\n"
                f"请确保已登录 OpenClaw，或在 llm_config.yaml 中更新 auth_profile_path"
            )
        data = json.loads(p.read_text(encoding="utf-8"))
        self._profile = data.get("profiles", {}).get("gongfeng:default", {})
        if not self._profile.get("access"):
            raise RuntimeError("[GongfengOAuth] 无效 token，请重新登录 OpenClaw")
        return self._profile

    def _make_headers(self) -> dict:
        p = self._load_profile()
        model_header = self._config.get("model_header") or self._config.get("model") or "GPT-5.4"
        return {
            "Authorization": f"Bearer {p['access']}",
            "OAUTH-TOKEN": p["access"],
            "X-Username": p.get("username", ""),
            "DEVICE-ID": p.get("deviceId", ""),
            "Content-Type": "application/json",
            "X-Model-Name": model_header,
        }

    def _get_http(self):
        if self._http is None:
            import httpx
            self._http = httpx.Client(timeout=self._config.get("timeout", 60))
        return self._http

    def chat_completions_create(self, model: str, messages: list, **kwargs) -> str:
        """OpenAI-style interface, returns content string"""
        base_url = self._config["base_url"].rstrip("/")
        payload = {
            "model": model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.1),
            "max_tokens": kwargs.get("max_tokens", 2000),
        }
        resp = self._get_http().post(
            f"{base_url}/chat/completions",
            json=payload,
            headers=self._make_headers(),
        )
        if resp.status_code == 401:
            raise RuntimeError("[GongfengOAuth] Token 已过期，请重新登录 OpenClaw")
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After") or resp.headers.get("retry-after")
            raise RuntimeError(f"[GongfengOAuth] RATE_LIMIT_429 retry_after={retry_after or ''}".strip())
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    def is_available(self) -> bool:
        """token 存在且非空即认为可用（不发网络请求）"""
        try:
            p = self._load_profile()
            return bool(p.get("access"))
        except Exception:
            return False


# ───────────────────────────────────────────────────────────────────
def _deep_merge(base: dict, override: dict) -> dict:
    """递归合并两个字典，override 中的值覆盖 base 中的同名键。"""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


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
                logger.debug(f"Environment variable '{var_name}' not set (provider not active)")
                return match.group(0)
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
    - 多 provider（gongfeng / xfyun / deepseek / openai 等）
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
        """加载并解析 LLM 配置文件
        
        支持本地覆盖：如果 config/llm_config.local.yaml 存在，
        会与 llm_config.yaml 合并（local 覆盖 default）。
        llm_config.local.yaml 应加入 .gitignore，不提交密钥。
        """
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

        # 检查是否有 local 覆盖文件
        base_path = Path(config_path)
        local_path = base_path.parent / "llm_config.local.yaml"
        if local_path.exists():
            with open(str(local_path), "r", encoding="utf-8") as f:
                local_config = yaml.safe_load(f) or {}
            raw_config = _deep_merge(raw_config, local_config)
            logger.info(f"[LLMClient] 已加载本地覆盖配置: {local_path}")

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

    def _get_or_create_client(self, provider_name: str, provider_config: dict):
        """获取或创建客户端实例（按 provider 缓存）

        工蜂AI provider 返回 GongfengOAuthClient（不是 OpenAI）。
        其他 provider 返回标准 OpenAI 实例。
        """
        if provider_name not in self._clients:
            auth_type = provider_config.get("auth_type", "api_key")

            if auth_type == "gongfeng_oauth":
                gc = GongfengOAuthClient(provider_config)
                if not gc.is_available():
                    # token 不可用，尝试 fallback
                    fallback = provider_config.get("fallback_provider")
                    if fallback:
                        logger.warning(
                            f"[LLMClient] 工蜂AI OAuth 不可用，自动降级到 {fallback}"
                        )
                        fb_config = self._config["providers"].get(fallback, {})
                        return self._get_or_create_client(fallback, fb_config)
                    raise RuntimeError(
                        "[LLMClient] 工蜂AI OAuth 不可用且无 fallback_provider 配置"
                    )
                self._clients[provider_name] = gc
                logger.info("[LLMClient] 工蜂AI OAuth 客户端已就绪")
            else:
                api_key = provider_config.get("api_key", "")
                base_url = provider_config.get("base_url")
                if not api_key or str(api_key).startswith("${"):
                    logger.warning(
                        f"Provider '{provider_name}' API key may not be set correctly: {api_key!r}"
                    )
                if base_url and str(base_url).startswith("${"):
                    raise RuntimeError(
                        f"Provider '{provider_name}' base_url is unresolved: {base_url!r}. "
                        f"Please set the required environment variable before running LLM flows."
                    )
                self._clients[provider_name] = OpenAI(api_key=api_key, base_url=base_url)
                logger.debug(f"Created OpenAI client for provider '{provider_name}' at {base_url}")

        return self._clients[provider_name]

    def _pick_fallback_provider(self, requested: List[str]) -> Optional[Tuple[str, dict]]:
        """按顺序选择第一个看起来可用的 fallback provider。"""
        providers = self._config.get("providers", {})
        for name in requested:
            cfg = providers.get(name)
            if not cfg:
                continue
            auth_type = cfg.get("auth_type", "api_key")
            if auth_type == "gongfeng_oauth":
                gc = GongfengOAuthClient(cfg)
                if gc.is_available():
                    return name, cfg
            else:
                api_key = cfg.get("api_key", "")
                if api_key and not str(api_key).startswith("${"):
                    return name, cfg
        return None

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        module_name: str = "default",
        _tried_fallback: bool = False,
        _forced_provider: Optional[str] = None,
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
        if _forced_provider:
            providers = self._config.get("providers", {})
            if _forced_provider not in providers:
                raise ValueError(f"Forced provider '{_forced_provider}' not found in config")
            provider_name = _forced_provider
            provider_config = dict(providers[_forced_provider])
            module_override = self._config.get("module_overrides", {}).get(module_name, {})
            for key, value in module_override.items():
                if key != "provider":
                    provider_config[key] = value
        else:
            provider_name, provider_config = self._get_provider_config(module_name)
        client = self._get_or_create_client(provider_name, provider_config)

        model = provider_config.get("model", "gongfeng/gpt-5-4")
        max_retries = provider_config.get("max_retries", 3)
        temperature = kwargs.pop("temperature", provider_config.get("temperature", 0.1))
        max_tokens = kwargs.pop("max_tokens", provider_config.get("max_tokens", 2000))

        last_exception: Optional[Exception] = None

        # ── 工蜂AI 分支（GongfengOAuthClient）───────────────────────────────
        if isinstance(client, GongfengOAuthClient):
            rate_limit_backoff = int(provider_config.get("rate_limit_backoff_seconds", 8))
            for attempt in range(1, max_retries + 1):
                try:
                    logger.debug(
                        f"LLM request [工蜂AI]: module={module_name}, "
                        f"attempt={attempt}/{max_retries}, model={model}"
                    )
                    content = client.chat_completions_create(
                        model=model, messages=messages,
                        temperature=temperature, max_tokens=max_tokens,
                    )
                    logger.debug(f"LLM response: {len(content)} chars")
                    return content
                except RuntimeError as e:
                    if "Token 已过期" in str(e):
                        raise
                    last_exception = e
                    logger.warning(f"[工蜂AI] 尝试 {attempt}/{max_retries} 失败: {e}")
                    if attempt < max_retries:
                        msg = str(e)
                        if "RATE_LIMIT_429" in msg:
                            m = re.search(r"retry_after=([0-9]+)", msg)
                            wait_s = int(m.group(1)) if m else rate_limit_backoff * attempt
                            logger.warning(f"[工蜂AI] 命中 429，等待 {wait_s}s 后重试")
                            time.sleep(wait_s)
                        else:
                            time.sleep(2 ** attempt)
                except Exception as e:
                    last_exception = e
                    logger.warning(f"[工蜂AI] 尝试 {attempt}/{max_retries} 异常: {e}")
                    if attempt < max_retries:
                        time.sleep(2 ** attempt)

            fallback_names = provider_config.get("fallback_providers") or []
            picked = None if _tried_fallback else self._pick_fallback_provider(fallback_names)
            if picked and ("429" in str(last_exception) or "Too Many Requests" in str(last_exception) or "RATE_LIMIT_429" in str(last_exception)):
                fallback, _fb_cfg = picked
                logger.warning(
                    f"[LLMClient] Provider '{provider_name}' rate-limited, "
                    f"switching to fallback_provider='{fallback}' for module='{module_name}'"
                )
                original_default = self._config.get("default_provider")
                try:
                    self._config["default_provider"] = fallback
                    overrides = self._config.setdefault("module_overrides", {})
                    module_override = dict(overrides.get(module_name, {}))
                    module_override["provider"] = fallback
                    overrides[module_name] = module_override
                    return self.chat_completion(
                        messages=messages,
                        module_name=module_name,
                        _tried_fallback=True,
                        _forced_provider=fallback,
                        **kwargs,
                    )
                finally:
                    self._config["default_provider"] = original_default

            raise RuntimeError(
                f"[工蜂AI] 调用失败，已重试 {max_retries} 次。Last: {last_exception}"
            ) from last_exception

        # ── 标准 OpenAI-compatible 分支─────────────────────────────────────
        timeout = provider_config.get("timeout", 60)
        request_params: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": timeout,
        }
        request_params.update(kwargs)

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
                wait_time = 10 * attempt
                logger.warning(
                    f"Rate limit on attempt {attempt}/{max_retries}. "
                    f"Waiting {wait_time}s before retry..."
                )
                if attempt < max_retries:
                    time.sleep(wait_time)

            except APIError as e:
                last_exception = e
                status_code = getattr(e, "status_code", None)
                message = getattr(e, "message", str(e))
                logger.error(
                    f"API error on attempt {attempt}/{max_retries}: "
                    f"status={status_code}, message={message}"
                )
                if status_code and 400 <= status_code < 500 and status_code != 429:
                    raise RuntimeError(
                        f"Non-retryable API error: {status_code} - {message}"
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
        """获取指定模块将使用的 provider 信息（脱敏），用于日志和调试。"""
        provider_name, config = self._get_provider_config(module_name)
        auth_type = config.get("auth_type", "api_key")
        if auth_type == "gongfeng_oauth":
            gc = GongfengOAuthClient(config)
            credential_ready = gc.is_available()
        else:
            credential_ready = bool(
                config.get("api_key") and not config.get("api_key", "").startswith("${")
            )
        return {
            "provider": provider_name,
            "auth_type": auth_type,
            "model": config.get("model"),
            "base_url": config.get("base_url"),
            "temperature": config.get("temperature"),
            "max_retries": config.get("max_retries"),
            "credential_ready": credential_ready,
            "api_key_set": credential_ready,
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
