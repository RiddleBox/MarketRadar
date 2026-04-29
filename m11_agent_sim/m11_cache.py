"""
m11_agent_sim/m11_cache.py — M11 验证结果缓存

降低 API 成本：相同输入在 TTL 内直接返回缓存结果。
"""

import hashlib
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class M11Cache:
    """M11 验证结果缓存"""

    def __init__(self, ttl_minutes: int = 10):
        """
        Args:
            ttl_minutes: 缓存有效期（分钟）
        """
        self.ttl_minutes = ttl_minutes
        self.cache_file = CACHE_DIR / "m11_cache.json"
        self._cache: Dict[str, dict] = {}
        self._load()

    def get(
        self,
        stock_code: str,
        signal_type: str,
        signal_content: str,
    ) -> Optional[dict]:
        """
        获取缓存的 M11 验证结果。

        Args:
            stock_code: 股票代码
            signal_type: 信号类型（如 "price_surge"）
            signal_content: 信号内容摘要

        Returns:
            {
                "consensus": bool,
                "vote_summary": {...},
                "cached_at": str,
            }
            或 None（缓存未命中或已过期）
        """
        cache_key = self._make_key(stock_code, signal_type, signal_content)
        entry = self._cache.get(cache_key)

        if not entry:
            return None

        # 检查是否过期
        cached_at = datetime.fromisoformat(entry["cached_at"])
        if datetime.now() - cached_at > timedelta(minutes=self.ttl_minutes):
            logger.debug(f"[M11Cache] 缓存过期 | key={cache_key[:16]}...")
            del self._cache[cache_key]
            self._save()
            return None

        logger.info(f"[M11Cache] 缓存命中 | stock={stock_code} type={signal_type}")
        return entry

    def set(
        self,
        stock_code: str,
        signal_type: str,
        signal_content: str,
        consensus: bool,
        vote_summary: dict,
    ):
        """
        保存 M11 验证结果到缓存。

        Args:
            stock_code: 股票代码
            signal_type: 信号类型
            signal_content: 信号内容摘要
            consensus: 是否达成共识
            vote_summary: 投票详情
        """
        cache_key = self._make_key(stock_code, signal_type, signal_content)
        self._cache[cache_key] = {
            "stock_code": stock_code,
            "signal_type": signal_type,
            "consensus": consensus,
            "vote_summary": vote_summary,
            "cached_at": datetime.now().isoformat(),
        }
        self._save()
        logger.info(f"[M11Cache] 缓存写入 | stock={stock_code} consensus={consensus}")

    def clear_expired(self):
        """清理过期缓存"""
        now = datetime.now()
        expired_keys = []
        for key, entry in self._cache.items():
            cached_at = datetime.fromisoformat(entry["cached_at"])
            if now - cached_at > timedelta(minutes=self.ttl_minutes):
                expired_keys.append(key)

        for key in expired_keys:
            del self._cache[key]

        if expired_keys:
            self._save()
            logger.info(f"[M11Cache] 清理过期缓存 {len(expired_keys)} 条")

    def stats(self) -> dict:
        """缓存统计"""
        total = len(self._cache)
        valid = 0
        now = datetime.now()
        for entry in self._cache.values():
            cached_at = datetime.fromisoformat(entry["cached_at"])
            if now - cached_at <= timedelta(minutes=self.ttl_minutes):
                valid += 1

        return {
            "total_entries": total,
            "valid_entries": valid,
            "expired_entries": total - valid,
            "ttl_minutes": self.ttl_minutes,
        }

    def _make_key(self, stock_code: str, signal_type: str, signal_content: str) -> str:
        """生成缓存键（基于输入内容的哈希）"""
        content = f"{stock_code}|{signal_type}|{signal_content}"
        return hashlib.sha256(content.encode()).hexdigest()

    def _load(self):
        """从文件加载缓存"""
        if self.cache_file.exists():
            try:
                data = json.loads(self.cache_file.read_text(encoding="utf-8"))
                self._cache = data
                logger.info(f"[M11Cache] 加载缓存 {len(self._cache)} 条")
            except Exception as e:
                logger.error(f"[M11Cache] 加载缓存失败: {e}")

    def _save(self):
        """保存缓存到文件"""
        self.cache_file.write_text(
            json.dumps(self._cache, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
