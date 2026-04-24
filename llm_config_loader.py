"""
LLM配置加载工具
支持多种配置格式: JSON、YAML
"""

import json
import yaml
from pathlib import Path
from typing import Dict, Optional
from m1_5_implicit_reasoner.llm_client import create_llm_client, LLMClient


def load_llm_config(config_path: Optional[str] = None) -> Dict:
    """
    加载LLM配置

    Args:
        config_path: 配置文件路径，默认优先级:
            1. llm_config.json (新格式)
            2. config/llm_config.local.yaml (现有格式)
            3. config/llm_config.yaml (现有格式)

    Returns:
        配置字典
    """
    if config_path is None:
        # 尝试多个配置文件路径
        possible_paths = [
            Path(__file__).parent / "llm_config.json",
            Path(__file__).parent / "config" / "llm_config.local.yaml",
            Path(__file__).parent / "config" / "llm_config.yaml",
        ]

        for path in possible_paths:
            if path.exists():
                config_path = path
                break

        if config_path is None:
            print("未找到配置文件，使用Mock LLM客户端")
            return {"provider": "mock"}
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        print(f"配置文件不存在: {config_path}")
        print("使用Mock LLM客户端")
        return {"provider": "mock"}

    # 根据文件扩展名加载
    if config_path.suffix == '.json':
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    elif config_path.suffix in ['.yaml', '.yml']:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    else:
        print(f"不支持的配置文件格式: {config_path.suffix}")
        return {"provider": "mock"}

    print(f"加载配置文件: {config_path}")
    return config


def create_llm_from_config(config_path: Optional[str] = None) -> LLMClient:
    """
    从配置文件创建LLM客户端

    Args:
        config_path: 配置文件路径

    Returns:
        LLM客户端实例
    """
    config = load_llm_config(config_path)

    # 处理新格式 (llm_config.json)
    if "provider" in config:
        provider = config.get("provider", "mock")

        if provider == "openai":
            openai_config = config.get("openai", {})
            return create_llm_client(
                provider="openai",
                api_key=openai_config.get("api_key"),
                model=openai_config.get("model", "gpt-4"),
                base_url=openai_config.get("base_url")
            )

        elif provider == "anthropic":
            anthropic_config = config.get("anthropic", {})
            return create_llm_client(
                provider="anthropic",
                api_key=anthropic_config.get("api_key"),
                model=anthropic_config.get("model", "claude-3-sonnet-20240229")
            )

        elif provider == "deepseek":
            # DeepSeek使用OpenAI兼容格式
            deepseek_config = config.get("deepseek", {})
            return create_llm_client(
                provider="openai",
                api_key=deepseek_config.get("api_key"),
                model=deepseek_config.get("model", "deepseek-chat"),
                base_url=deepseek_config.get("base_url", "https://api.deepseek.com")
            )

        else:
            print(f"使用Mock LLM客户端（provider={provider}）")
            return create_llm_client(provider="mock")

    # 处理现有格式 (llm_config.yaml)
    elif "default_provider" in config:
        default_provider = config.get("default_provider", "mock")
        providers = config.get("providers", {})

        if default_provider in providers:
            provider_config = providers[default_provider]

            if default_provider == "deepseek":
                # DeepSeek使用OpenAI兼容格式
                return create_llm_client(
                    provider="openai",
                    api_key=provider_config.get("api_key"),
                    model=provider_config.get("model", "deepseek-chat"),
                    base_url=provider_config.get("base_url", "https://api.deepseek.com")
                )

            elif default_provider == "openai":
                return create_llm_client(
                    provider="openai",
                    api_key=provider_config.get("api_key"),
                    model=provider_config.get("model", "gpt-4"),
                    base_url=provider_config.get("base_url")
                )

            elif default_provider == "anthropic":
                return create_llm_client(
                    provider="anthropic",
                    api_key=provider_config.get("api_key"),
                    model=provider_config.get("model", "claude-3-sonnet-20240229")
                )

        print(f"使用Mock LLM客户端（default_provider={default_provider}）")
        return create_llm_client(provider="mock")

    else:
        print("配置格式不正确，使用Mock LLM客户端")
        return create_llm_client(provider="mock")


if __name__ == "__main__":
    # 测试配置加载
    print("测试LLM配置加载...")

    config = load_llm_config()
    print(f"\n配置提供商: {config.get('provider')}")

    client = create_llm_from_config()
    print(f"LLM客户端类型: {type(client).__name__}")

    # 测试调用
    print("\n测试LLM调用...")
    try:
        response = client.chat("你好，请用一句话介绍你自己。")
        print(f"响应: {response[:100]}...")
    except Exception as e:
        print(f"调用失败: {e}")
