"""
m0_collector/dedup.py — 去重索引

基于 URL + 内容 hash 双重校验，防止同一条信息被多次写入 incoming/。
索引持久化为 manifest/dedup_index.json。
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Set

logger = logging.getLogger(__name__)

DEFAULT_INDEX_PATH = Path(__file__).parent / "manifest" / "dedup_index.json"


class DedupIndex:
    """去重索引，基于 URL 和内容 hash 双重判断。"""

    def __init__(self, index_path: Path = DEFAULT_INDEX_PATH):
        self.index_path = index_path
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self._urls: Set[str] = set()
        self._hashes: Set[str] = set()
        self._load()

    def is_duplicate(self, url: str, content: str) -> bool:
        """判断是否重复：URL 或内容 hash 任一命中即视为重复。"""
        if url and url in self._urls:
            return True
        h = self._content_hash(content)
        return h in self._hashes

    def add(self, url: str, content: str) -> str:
        """加入索引，返回内容 hash（用于文件名）。"""
        if url:
            self._urls.add(url)
        h = self._content_hash(content)
        self._hashes.add(h)
        return h

    def save(self):
        """持久化索引到磁盘。"""
        data = {
            "urls": sorted(self._urls),
            "hashes": sorted(self._hashes),
        }
        self.index_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(f"[Dedup] 索引已保存: urls={len(self._urls)} hashes={len(self._hashes)}")

    def stats(self) -> dict:
        return {"url_count": len(self._urls), "hash_count": len(self._hashes)}

    def _load(self):
        if self.index_path.exists():
            try:
                data = json.loads(self.index_path.read_text(encoding="utf-8"))
                self._urls = set(data.get("urls", []))
                self._hashes = set(data.get("hashes", []))
                logger.info(f"[Dedup] 加载索引: urls={len(self._urls)} hashes={len(self._hashes)}")
            except Exception as e:
                logger.warning(f"[Dedup] 索引加载失败，从空开始: {e}")

    @staticmethod
    def _content_hash(content: str) -> str:
        """内容前 500 字符的 MD5（截断避免微小差异导致误判）"""
        normalized = " ".join(content[:500].split())
        return hashlib.md5(normalized.encode("utf-8")).hexdigest()[:16]
