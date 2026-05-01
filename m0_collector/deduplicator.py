"""
m0_collector/deduplicator.py — 新闻去重器（基于SQLite）

职责：
  1. 基于 URL 去重（主键）
  2. 基于标题相似度去重（编辑距离）
  3. 记录已处理的新闻，避免重复触发信号

表结构：
  - processed_news: (url PRIMARY KEY, title, source, collected_at, title_hash)
"""

import hashlib
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class NewsDeduplicator:
    """新闻去重器（基于SQLite）"""

    def __init__(self, db_path: str = "data/news_dedup.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """初始化数据库表结构"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_news (
                url TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                source TEXT NOT NULL,
                collected_at TEXT NOT NULL,
                title_hash TEXT NOT NULL
            )
        """)

        # 为 title_hash 创建索引（加速相似标题查询）
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_title_hash 
            ON processed_news(title_hash)
        """)

        conn.commit()
        conn.close()

    def _compute_title_hash(self, title: str) -> str:
        """计算标题哈希（用于快速相似度检查）"""
        # 移除空格、标点，转小写
        normalized = "".join(c.lower() for c in title if c.isalnum())
        return hashlib.md5(normalized.encode()).hexdigest()

    def is_duplicate(self, url: str, title: str, source: str) -> bool:
        """
        检查新闻是否重复
        
        Args:
            url: 新闻URL
            title: 新闻标题
            source: 新闻来源
            
        Returns:
            True: 重复（已处理过）
            False: 新新闻（需要处理）
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 1. 检查 URL 是否存在（精确匹配）
        cursor.execute("SELECT 1 FROM processed_news WHERE url = ?", (url,))
        if cursor.fetchone():
            conn.close()
            logger.debug(f"[去重] URL已存在: {url}")
            return True

        # 2. 检查标题哈希是否存在（相似标题）
        title_hash = self._compute_title_hash(title)
        cursor.execute(
            "SELECT title, url FROM processed_news WHERE title_hash = ?",
            (title_hash,)
        )
        similar = cursor.fetchone()
        if similar:
            conn.close()
            logger.debug(f"[去重] 相似标题已存在: {title} ≈ {similar[0]}")
            return True

        conn.close()
        return False

    def mark_processed(self, url: str, title: str, source: str):
        """
        标记新闻为已处理
        
        Args:
            url: 新闻URL
            title: 新闻标题
            source: 新闻来源
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        title_hash = self._compute_title_hash(title)
        collected_at = datetime.now().isoformat()

        try:
            cursor.execute("""
                INSERT INTO processed_news (url, title, source, collected_at, title_hash)
                VALUES (?, ?, ?, ?, ?)
            """, (url, title, source, collected_at, title_hash))
            conn.commit()
            logger.debug(f"[去重] 标记已处理: {title}")
        except sqlite3.IntegrityError:
            # URL 已存在（并发场景）
            logger.warning(f"[去重] URL已存在（并发插入）: {url}")
        finally:
            conn.close()

    def get_stats(self) -> dict:
        """获取去重统计信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM processed_news")
        total = cursor.fetchone()[0]

        cursor.execute("""
            SELECT source, COUNT(*) 
            FROM processed_news 
            GROUP BY source
        """)
        by_source = dict(cursor.fetchall())

        conn.close()

        return {
            "total_processed": total,
            "by_source": by_source
        }

    def cleanup_old_records(self, days: int = 30):
        """
        清理旧记录（可选，避免数据库无限增长）
        
        Args:
            days: 保留最近N天的记录
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff = cutoff.replace(day=cutoff.day - days)
        cutoff_str = cutoff.isoformat()

        cursor.execute("""
            DELETE FROM processed_news 
            WHERE collected_at < ?
        """, (cutoff_str,))

        deleted = cursor.rowcount
        conn.commit()
        conn.close()

        logger.info(f"[去重] 清理 {deleted} 条旧记录（>{days}天）")
        return deleted
