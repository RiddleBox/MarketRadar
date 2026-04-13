"""
m0_collector/models.py — 收集层数据模型

RawArticle:   Provider 层原始抓取结果，格式不保证
CollectedItem: 标准化后写入 data/incoming/ 的契约格式
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class RawArticle:
    """Provider 层原始文章，格式未经标准化。"""
    title: str
    content: str                    # 正文（可能含 HTML，normalizer 负责清洗）
    raw_published_at: str           # 原始时间字符串，格式不保证
    source_name: str                # 来源名称，如 "财联社"、"东方财富"
    source_url: str                 # 原文链接（去重主键）
    provider_id: str                # 来自哪个 Provider
    language: str = "zh"           # zh / en
    extra: dict = field(default_factory=dict)  # Provider 私有扩展字段


@dataclass
class CollectedItem:
    """
    标准化后的收集记录。
    直接写入 data/incoming/<filename>.txt，被 pipeline/ingest.py 消费。

    文件名规则：YYYYMMDD_<provider>_<hash8>.txt
    """
    item_id: str                    # hash8，用于文件名和去重
    title: str
    content: str                    # 清洗后正文
    published_at: datetime          # 事件时间（解析后）
    collected_at: datetime          # 收集时间
    source_name: str
    source_url: str
    provider_id: str
    language: str = "zh"

    def to_text(self) -> str:
        """序列化为写入 incoming/ 的文本格式。

        格式：标题 + 元数据注释行 + 正文
        pipeline/ingest.py 只需读取文本内容，元数据行供人工审查。
        """
        meta = (
            f"<!-- source: {self.source_name} | "
            f"url: {self.source_url} | "
            f"published: {self.published_at.strftime('%Y-%m-%d %H:%M')} | "
            f"collected: {self.collected_at.strftime('%Y-%m-%d %H:%M')} | "
            f"provider: {self.provider_id} -->"
        )
        return f"【{self.source_name}】{self.title}\n\n{meta}\n\n{self.content}"

    def filename(self) -> str:
        """生成写入 incoming/ 的文件名。"""
        date_str = self.published_at.strftime("%Y%m%d")
        return f"{date_str}_{self.provider_id}_{self.item_id}.txt"
