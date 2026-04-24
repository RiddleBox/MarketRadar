"""
LLM客户端抽象层
支持多种LLM提供商: OpenAI, Anthropic, 本地模型
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import json


class LLMClient(ABC):
    """LLM客户端抽象接口"""

    @abstractmethod
    def chat(self, prompt: str, **kwargs) -> str:
        """
        发送聊天请求

        Args:
            prompt: 提示词
            **kwargs: 额外参数（temperature, max_tokens等）

        Returns:
            LLM响应文本
        """
        pass

    @abstractmethod
    def chat_json(self, prompt: str, **kwargs) -> Dict:
        """
        发送聊天请求并解析JSON响应

        Args:
            prompt: 提示词
            **kwargs: 额外参数

        Returns:
            解析后的JSON对象
        """
        pass


class OpenAIClient(LLMClient):
    """OpenAI客户端"""

    def __init__(self, api_key: str, model: str = "gpt-4", base_url: Optional[str] = None):
        """
        初始化OpenAI客户端

        Args:
            api_key: API密钥
            model: 模型名称
            base_url: API基础URL（用于兼容OpenAI格式的本地模型）
        """
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key, base_url=base_url)
        except ImportError:
            raise ImportError("请安装openai库: pip install openai")

    def chat(self, prompt: str, **kwargs) -> str:
        """发送聊天请求"""
        temperature = kwargs.get('temperature', 0.7)
        max_tokens = kwargs.get('max_tokens', 2000)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens
        )

        return response.choices[0].message.content

    def chat_json(self, prompt: str, **kwargs) -> Dict:
        """发送聊天请求并解析JSON"""
        response_text = self.chat(prompt, **kwargs)

        # 尝试解析JSON
        try:
            # 提取JSON部分（可能包含在markdown代码块中）
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            else:
                json_text = response_text.strip()

            return json.loads(json_text)
        except json.JSONDecodeError as e:
            print(f"JSON解析失败: {e}")
            print(f"原始响应: {response_text}")
            return {}


class AnthropicClient(LLMClient):
    """Anthropic客户端"""

    def __init__(self, api_key: str, model: str = "claude-3-sonnet-20240229"):
        """
        初始化Anthropic客户端

        Args:
            api_key: API密钥
            model: 模型名称
        """
        self.api_key = api_key
        self.model = model

        try:
            from anthropic import Anthropic
            self.client = Anthropic(api_key=api_key)
        except ImportError:
            raise ImportError("请安装anthropic库: pip install anthropic")

    def chat(self, prompt: str, **kwargs) -> str:
        """发送聊天请求"""
        temperature = kwargs.get('temperature', 0.7)
        max_tokens = kwargs.get('max_tokens', 2000)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        return response.content[0].text

    def chat_json(self, prompt: str, **kwargs) -> Dict:
        """发送聊天请求并解析JSON"""
        response_text = self.chat(prompt, **kwargs)

        try:
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            else:
                json_text = response_text.strip()

            return json.loads(json_text)
        except json.JSONDecodeError as e:
            print(f"JSON解析失败: {e}")
            print(f"原始响应: {response_text}")
            return {}


class MockLLMClient(LLMClient):
    """Mock LLM客户端（用于测试）"""

    def __init__(self):
        """初始化Mock客户端"""
        pass

    def chat(self, prompt: str, **kwargs) -> str:
        """返回模拟响应"""
        return """
{
    "event_analysis": {
        "core_event": "沙特王储访华，签署新能源合作协议",
        "key_entities": ["沙特", "中国", "新能源", "光伏"],
        "time_sensitivity": "high",
        "importance_score": 0.85
    },
    "causal_chain": [
        {
            "from_concept": "外交访问",
            "to_concept": "能源合作协议",
            "relation_type": "policy_drives",
            "reasoning": "高层外交访问通常伴随重要合作协议签署",
            "confidence": 0.9,
            "supporting_facts": ["历史外交访问记录"]
        },
        {
            "from_concept": "能源合作协议",
            "to_concept": "光伏项目出口",
            "relation_type": "demand_shifts",
            "reasoning": "中东地区光照资源丰富，新能源合作重点在光伏",
            "confidence": 0.8,
            "supporting_facts": ["中东光照条件优越", "沙特2030愿景"]
        }
    ],
    "industry_impact": {
        "affected_sectors": [
            {
                "sector_name": "光伏组件",
                "impact_path": "downstream",
                "impact_strength": 0.85,
                "timeframe": "mid_term"
            }
        ]
    },
    "target_identification": {
        "opportunities": [
            {
                "industry_sector": "光伏中游",
                "target_symbols": ["601012.SH", "688599.SH"],
                "opportunity_description": "中东市场光伏组件出口机会",
                "benefit_logic": "合作协议可能带来大额订单",
                "confidence": 0.75
            }
        ]
    },
    "overall_assessment": {
        "signal_type": "diplomatic_event",
        "overall_confidence": 0.75,
        "key_risks": ["协议落地不确定性", "地缘政治风险"]
    }
}
"""

    def chat_json(self, prompt: str, **kwargs) -> Dict:
        """返回模拟JSON响应"""
        response_text = self.chat(prompt, **kwargs)
        return json.loads(response_text)


def create_llm_client(
    provider: str = "mock",
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    **kwargs
) -> LLMClient:
    """
    工厂函数：创建LLM客户端

    Args:
        provider: 提供商 (openai, anthropic, mock)
        api_key: API密钥
        model: 模型名称
        **kwargs: 额外参数

    Returns:
        LLM客户端实例
    """
    if provider == "openai":
        if not api_key:
            raise ValueError("OpenAI需要api_key")
        return OpenAIClient(
            api_key=api_key,
            model=model or "gpt-4",
            base_url=kwargs.get('base_url')
        )

    elif provider == "anthropic":
        if not api_key:
            raise ValueError("Anthropic需要api_key")
        return AnthropicClient(
            api_key=api_key,
            model=model or "claude-3-sonnet-20240229"
        )

    elif provider == "mock":
        return MockLLMClient()

    else:
        raise ValueError(f"未知的提供商: {provider}")
