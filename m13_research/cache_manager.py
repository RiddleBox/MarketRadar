"""
m13_research/cache_manager.py — 缓存管理器

核心职责：
1. 缓存读写
2. 过期检查
3. 缓存清除
4. 缓存统计
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from core.schemas import ResearchReport

logger = logging.getLogger(__name__)


class CacheManager:
    """缓存管理器"""

    # 缓存TTL（小时）
    TTL_MAP = {
        'quick': 6,      # Level 1: 6小时
        'standard': 12,  # Level 2: 12小时
        'deep': 24       # Level 3: 24小时
    }

    def __init__(self, cache_dir: Path):
        """
        初始化缓存管理器

        Args:
            cache_dir: 缓存目录
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"[M13 Cache] 初始化缓存目录: {self.cache_dir}")

    def get(self, symbol: str, level: str) -> Optional[ResearchReport]:
        """
        获取缓存

        Args:
            symbol: 股票代码
            level: 调研级别

        Returns:
            调研报告或None
        """
        cache_key = self._build_key(symbol, level)
        cache_file = self.cache_dir / f"{cache_key}.json"

        if not cache_file.exists():
            return None

        # 检查是否过期
        if self._is_expired(cache_file, level):
            logger.info(f"[M13 Cache] 缓存过期，删除: {cache_key}")
            cache_file.unlink()
            return None

        # 读取缓存
        try:
            data = json.loads(cache_file.read_text(encoding='utf-8'))

            # 转换datetime字段
            if 'research_time' in data and isinstance(data['research_time'], str):
                data['research_time'] = datetime.fromisoformat(data['research_time'])

            report = ResearchReport(**data)
            report.cache_hit = True

            logger.info(f"[M13 Cache] 命中缓存: {cache_key}")
            return report

        except Exception as e:
            logger.error(f"[M13 Cache] 读取缓存失败: {cache_key} - {e}")
            cache_file.unlink()
            return None

    def set(self, report: ResearchReport):
        """
        保存缓存

        Args:
            report: 调研报告
        """
        cache_key = self._build_key(report.symbol, report.research_level.value)
        cache_file = self.cache_dir / f"{cache_key}.json"

        try:
            # 转换为字典
            data = report.model_dump()

            # 转换datetime为字符串
            if 'research_time' in data and isinstance(data['research_time'], datetime):
                data['research_time'] = data['research_time'].isoformat()

            # 写入文件
            cache_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2, default=str),
                encoding='utf-8'
            )

            logger.info(f"[M13 Cache] 保存缓存: {cache_key}")

        except Exception as e:
            logger.error(f"[M13 Cache] 保存缓存失败: {cache_key} - {e}")

    def invalidate(self, symbol: str):
        """
        清除指定标的的所有缓存

        Args:
            symbol: 股票代码
        """
        count = 0
        for level in ['quick', 'standard', 'deep']:
            cache_key = self._build_key(symbol, level)
            cache_file = self.cache_dir / f"{cache_key}.json"

            if cache_file.exists():
                cache_file.unlink()
                count += 1

        if count > 0:
            logger.info(f"[M13 Cache] 清除缓存: {symbol} ({count}个文件)")

    def invalidate_all(self):
        """清除所有缓存"""
        count = 0
        for cache_file in self.cache_dir.glob("research_*.json"):
            cache_file.unlink()
            count += 1

        logger.info(f"[M13 Cache] 清除所有缓存: {count}个文件")

    def get_stats(self) -> dict:
        """
        获取缓存统计

        Returns:
            统计信息
        """
        stats = {
            'total_files': 0,
            'by_level': {'quick': 0, 'standard': 0, 'deep': 0},
            'expired': 0,
            'total_size_mb': 0.0
        }

        total_size = 0
        for cache_file in self.cache_dir.glob("research_*.json"):
            stats['total_files'] += 1
            total_size += cache_file.stat().st_size

            # 统计级别
            for level in ['quick', 'standard', 'deep']:
                if f"_{level}_" in cache_file.name:
                    stats['by_level'][level] += 1

                    # 检查是否过期
                    if self._is_expired(cache_file, level):
                        stats['expired'] += 1
                    break

        stats['total_size_mb'] = round(total_size / 1024 / 1024, 2)
        return stats

    def cleanup_expired(self):
        """清理过期缓存"""
        count = 0
        for cache_file in self.cache_dir.glob("research_*.json"):
            # 从文件名提取level
            for level in ['quick', 'standard', 'deep']:
                if f"_{level}_" in cache_file.name:
                    if self._is_expired(cache_file, level):
                        cache_file.unlink()
                        count += 1
                    break

        if count > 0:
            logger.info(f"[M13 Cache] 清理过期缓存: {count}个文件")

    def _build_key(self, symbol: str, level: str) -> str:
        """
        构建缓存键

        Args:
            symbol: 股票代码
            level: 调研级别

        Returns:
            缓存键
        """
        date = datetime.now().strftime("%Y%m%d")
        return f"research_{symbol}_{level}_{date}"

    def _is_expired(self, cache_file: Path, level: str) -> bool:
        """
        检查是否过期

        Args:
            cache_file: 缓存文件
            level: 调研级别

        Returns:
            是否过期
        """
        try:
            mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
            age = datetime.now() - mtime
            ttl_hours = self.TTL_MAP.get(level, 12)
            return age.total_seconds() > ttl_hours * 3600
        except Exception as e:
            logger.error(f"检查缓存过期失败: {e}")
            return True
