"""
m0_collector/providers/base.py — Provider 抽象基类

新增数据来源只需继承此类，实现 fetch() 和 provider_id。
不需要改 normalizer / cli / 任何其他代码。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from m0_collector.models import RawArticle


class ProviderAdapter(ABC):
    """所有数据来源适配器的抽象基类。"""

    @abstractmethod
    def fetch(self, **kwargs) -> List[RawArticle]:
        """
        拉取数据，返回 RawArticle 列表。
        kwargs 由各 Provider 自行定义（date / limit / query 等）。
        单个条目失败不应抛异常，应记录日志并跳过。
        """
        ...

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Provider 唯一标识，写入 CollectedItem.provider_id，也用于文件名。"""
        ...

    @property
    def display_name(self) -> str:
        """人类可读名称，默认同 provider_id。"""
        return self.provider_id
