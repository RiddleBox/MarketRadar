"""
m0_collector/normalizer.py — 标准化层

职责：
  1. 解析 RawArticle 的时间字符串 → datetime
  2. 清洗内容（去除多余空白、HTML 残留等）
  3. 去重判断
  4. 生成 CollectedItem（包含 item_id / filename）
"""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List, Optional, Tuple

from m0_collector.dedup import DedupIndex
from m0_collector.models import CollectedItem, RawArticle

logger = logging.getLogger(__name__)


class Normalizer:
    """将 RawArticle 标准化为 CollectedItem。"""

    def __init__(self, dedup_index: DedupIndex):
        self.dedup = dedup_index

    def normalize(
        self,
        articles: List[RawArticle],
        force_reimport: bool = False,
    ) -> Tuple[List[CollectedItem], int, int]:
        """
        批量标准化。

        Args:
            articles: 原始文章列表
            force_reimport: 跳过去重检查

        Returns:
            (collected_items, skip_count, error_count)
        """
        items: List[CollectedItem] = []
        skip_count = 0
        error_count = 0

        for article in articles:
            try:
                # 去重检查
                if not force_reimport and self.dedup.is_duplicate(article.source_url, article.content):
                    logger.debug(f"[Normalizer] 去重跳过: {article.title[:40]}")
                    skip_count += 1
                    continue

                item = self._normalize_one(article)
                if item is None:
                    error_count += 1
                    continue

                # 加入去重索引
                self.dedup.add(article.source_url, article.content)
                items.append(item)

            except Exception as e:
                logger.warning(f"[Normalizer] 标准化失败: {article.title[:40]} | {e}")
                error_count += 1

        logger.info(
            f"[Normalizer] 标准化完成: 可导出={len(items)} 去重跳过={skip_count} 错误={error_count}"
        )
        return items, skip_count, error_count

    def _normalize_one(self, article: RawArticle) -> Optional[CollectedItem]:
        """标准化单条文章"""
        # 解析时间
        published_at = self._parse_datetime(article.raw_published_at)

        # 清洗内容
        content = self._clean_text(article.content)
        if len(content) < 20:
            logger.debug(f"[Normalizer] 内容过短跳过: {article.title[:40]}")
            return None

        # 生成 item_id（内容 hash 前8位）
        item_id = hashlib.md5(
            (article.source_url or content[:200]).encode("utf-8")
        ).hexdigest()[:8]

        return CollectedItem(
            item_id=item_id,
            title=article.title.strip(),
            content=content,
            published_at=published_at,
            collected_at=datetime.now(),
            source_name=article.source_name,
            source_url=article.source_url,
            provider_id=article.provider_id,
            language=article.language,
        )

    def _parse_datetime(self, raw: str) -> datetime:
        """解析各种格式的时间字符串，失败则返回当前时间"""
        if not raw:
            return datetime.now()

        # RFC 2822（RSS 标准）
        try:
            return parsedate_to_datetime(raw).replace(tzinfo=None)
        except Exception:
            pass

        # ISO 8601
        for fmt in [
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%Y/%m/%d %H:%M",
            "%Y年%m月%d日 %H:%M",
            "%Y年%m月%d日",
        ]:
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                continue

        logger.debug(f"[Normalizer] 时间解析失败，使用当前时间: {raw}")
        return datetime.now()

    def _clean_text(self, text: str) -> str:
        """清洗文本：去除多余空白、控制字符等"""
        if not text:
            return ""
        # 去除零宽字符
        text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)
        # 合并多余空行（超过2个换行合并为2个）
        text = re.sub(r"\n{3,}", "\n\n", text)
        # 合并行内多余空格
        text = re.sub(r"[ \t]{2,}", " ", text)
        return text.strip()
