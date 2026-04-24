"""
LLM配置加载工具
"""

import json
from pathlib import Path
from typing import Dict, Optional
from m1_5_implicit_reasoner.llm_client import create_llm_client, LLMClient


def load_llm_config(config_path: Optional[str] = None) -> Dict:
    """
    加载LLM配置

    Args:
        config_path: 配置文件路径，默认为项目根目录的llm_config.json

    Returns:
        配置字典
    """
    if config_path is None:
        config_path = Path(__file__).parent / "llm_config.json"
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        print(f"配置文件不存在: {config_path}")
        print("使用Mock LLM客户端")
        return {"provider": "mock"}

    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

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

    else:
        print(f"使用Mock LLM客户端（provider={provider}）")
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
