"""
m0_collector/providers/manual.py — 手动文本输入 Provider

场景：
  1. 命令行直接粘贴一段新闻文本
  2. 指定本地 .txt 文件导入
  3. 指定已有的 data/incoming/ 目录文件（re-ingest）

这是最简单的 Provider，主要用于：
  - 快速测试 pipeline
  - 人工研判的高质量文本
  - 无法通过 RSS 获取的付费报告摘录
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from m0_collector.models import RawArticle
from m0_collector.providers.base import ProviderAdapter

logger = logging.getLogger(__name__)


class ManualProvider(ProviderAdapter):
    """手动输入 Provider

    支持三种输入方式（优先级从高到低）：
    1. text 参数：直接传入文本字符串
    2. file 参数：读取本地文件
    3. stdin：从标准输入读取（适合管道操作）
    """

    def __init__(self, source_name: str = "手动输入"):
        self.source_name = source_name

    @property
    def provider_id(self) -> str:
        return "manual"

    @property
    def display_name(self) -> str:
        return "手动输入"

    def fetch(
        self,
        text: Optional[str] = None,
        file: Optional[str] = None,
        title: Optional[str] = None,
        source_name: Optional[str] = None,
        source_url: Optional[str] = None,
        published_at: Optional[str] = None,
        **kwargs,
    ) -> List[RawArticle]:
        """
        Args:
            text: 直接传入的文本内容
            file: 本地文件路径（.txt）
            title: 手动指定标题（可选）
            source_name: 来源名称（可选，默认"手动输入"）
            source_url: 原文链接（可选）
            published_at: 发布时间字符串（可选，默认当前时间）
        """
        content = ""
        if text:
            content = text.strip()
        elif file:
            fp = Path(file)
            if not fp.exists():
                raise FileNotFoundError(f"文件不存在: {file}")
            content = fp.read_text(encoding="utf-8").strip()
        else:
            # 从 stdin 读取
            logger.info("[Manual] 从 stdin 读取，请粘贴内容后按 Ctrl+D（或 Ctrl+Z）结束：")
            content = sys.stdin.read().strip()

        if not content:
            logger.warning("[Manual] 内容为空，返回空列表")
            return []

        # 从内容第一行提取标题（如果没有显式指定）
        lines = content.splitlines()
        if not title:
            first_line = lines[0].strip()
            # 如果第一行较短（<100字符），视为标题
            title = first_line if len(first_line) < 100 else "手动输入文本"

        return [RawArticle(
            title=title,
            content=content,
            raw_published_at=published_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            source_name=source_name or self.source_name,
            source_url=source_url or "",
            provider_id=self.provider_id,
            language="zh",
        )]
