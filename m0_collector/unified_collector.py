"""
统一新闻采集任务

使用新的 Data Provider Architecture 进行多源新闻采集。
替代原有的 _task_news_collect 和 _task_rss_news_collect。

特性：
- 多源聚合（A-stock SKILL + RSS）
- 自动去重
- 信号分类（explicit/implicit）
- 健康检查
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List
import sys

# 确保项目根目录在路径中
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from integrations.data_provider_manager import get_global_data_manager
from integrations.init_data_providers import initialize_data_providers
from m0_collector.models import CollectedItem
from m0_collector.dedup import DedupIndex
import hashlib

logger = logging.getLogger(__name__)


class UnifiedNewsCollector:
    """统一新闻采集器 - 使用 Data Provider Architecture"""

    def __init__(self):
        self.manager = None
        self.dedup_index = None
        self.incoming_dir = ROOT / "data" / "incoming"
        self.dedup_index_path = ROOT / "m0_collector" / "manifest" / "dedup_index.json"

    def initialize(self) -> bool:
        """初始化数据提供者和去重索引"""
        try:
            # 初始化数据提供者
            if not initialize_data_providers():
                logger.error("数据提供者初始化失败")
                return False

            self.manager = get_global_data_manager()

            # 初始化去重索引
            self.dedup_index = DedupIndex(self.dedup_index_path)

            # 确保目录存在
            self.incoming_dir.mkdir(parents=True, exist_ok=True)

            logger.info("✅ 统一新闻采集器初始化成功")
            return True

        except Exception as e:
            logger.error(f"❌ 统一新闻采集器初始化失败: {e}")
            return False

    def collect_macro_news(self, limit: int = 50) -> Dict:
        """
        采集宏观新闻（隐式推理信号）

        Args:
            limit: 最多采集数量

        Returns:
            采集结果统计
        """
        if not self.manager:
            return {"error": "未初始化", "fetched": 0, "written": 0}

        try:
            # 从多个提供者聚合宏观新闻
            news_list = self.manager.get_news(
                symbol=None,  # None = 宏观新闻
                limit=limit,
                providers=['astock_skill', 'rss'],  # 使用两个源
                aggregate=True  # 聚合模式
            )

            logger.info(f"📰 获取到 {len(news_list)} 条宏观新闻")

            # 转换为 NewsItem 并写入
            written = 0
            skipped = 0

            for news in news_list:
                # 去重检查
                if self.dedup_index and self.dedup_index.is_duplicate(
                    news.get('url', ''),
                    news['content']
                ):
                    skipped += 1
                    continue

                # 创建 CollectedItem
                item = self._create_collected_item(news)

                # 写入文件
                fname = self.incoming_dir / item.filename()
                if not fname.exists():
                    fname.write_text(item.to_text(), encoding="utf-8")
                    written += 1

                    # 更新去重索引
                    if self.dedup_index:
                        self.dedup_index.add(news.get('url', ''), news['content'])

            # 保存去重索引
            if self.dedup_index:
                self.dedup_index.save()

            logger.info(f"✅ 宏观新闻采集完成: 获取 {len(news_list)} 条, 写入 {written} 条, 去重跳过 {skipped} 条")

            return {
                "status": "success",
                "fetched": len(news_list),
                "written": written,
                "skipped": skipped,
                "type": "macro"
            }

        except Exception as e:
            logger.error(f"❌ 宏观新闻采集失败: {e}", exc_info=True)
            return {
                "status": "failed",
                "error": str(e),
                "fetched": 0,
                "written": 0
            }

    def collect_stock_news(self, symbols: List[str], limit_per_stock: int = 10) -> Dict:
        """
        采集个股新闻（显式信号）

        Args:
            symbols: 股票代码列表
            limit_per_stock: 每只股票最多采集数量

        Returns:
            采集结果统计
        """
        if not self.manager:
            return {"error": "未初始化", "fetched": 0, "written": 0}

        try:
            total_fetched = 0
            total_written = 0
            total_skipped = 0

            for symbol in symbols:
                # 获取个股新闻
                news_list = self.manager.get_news(
                    symbol=symbol,
                    limit=limit_per_stock,
                    providers=['astock_skill'],  # 个股新闻只用 SKILL
                    aggregate=False  # 单源模式
                )

                total_fetched += len(news_list)

                # 转换为 NewsItem 并写入
                for news in news_list:
                    # 去重检查
                    if self.dedup_index and self.dedup_index.is_duplicate(
                        news.get('url', ''),
                        news['content']
                    ):
                        total_skipped += 1
                        continue

                    # 创建 CollectedItem（添加股票代码到标题）
                    item = self._create_collected_item(news, related_symbol=symbol)

                    # 写入文件
                    fname = self.incoming_dir / item.filename()
                    if not fname.exists():
                        fname.write_text(item.to_text(), encoding="utf-8")
                        total_written += 1

                        # 更新去重索引
                        if self.dedup_index:
                            self.dedup_index.add(news.get('url', ''), news['content'])

            # 保存去重索引
            if self.dedup_index:
                self.dedup_index.save()

            logger.info(f"✅ 个股新闻采集完成: {len(symbols)} 只股票, 获取 {total_fetched} 条, 写入 {total_written} 条, 去重跳过 {total_skipped} 条")

            return {
                "status": "success",
                "fetched": total_fetched,
                "written": total_written,
                "skipped": total_skipped,
                "type": "explicit",
                "symbols_count": len(symbols)
            }

        except Exception as e:
            logger.error(f"❌ 个股新闻采集失败: {e}", exc_info=True)
            return {
                "status": "failed",
                "error": str(e),
                "fetched": 0,
                "written": 0
            }

    def health_check(self) -> Dict[str, bool]:
        """检查所有数据提供者健康状态"""
        if not self.manager:
            return {}
        return self.manager.health_check()

    def _create_collected_item(self, news: Dict, related_symbol: str = None) -> CollectedItem:
        """
        将新闻数据转换为 CollectedItem

        Args:
            news: 新闻字典
            related_symbol: 关联股票代码（个股新闻）

        Returns:
            CollectedItem 实例
        """
        # 生成 item_id（8位hash）
        content_hash = hashlib.md5(
            f"{news['title']}_{news['published_at']}".encode('utf-8')
        ).hexdigest()[:8]

        # 如果是个股新闻，在标题前添加股票代码
        title = news['title']
        if related_symbol:
            title = f"[{related_symbol}] {title}"

        # 在内容中添加信号类型标记
        content = news['content']
        signal_type = news.get('type', 'unknown')
        content = f"[信号类型: {signal_type}]\n\n{content}"

        return CollectedItem(
            item_id=content_hash,
            title=title,
            content=content,
            published_at=self._parse_datetime(news['published_at']),
            collected_at=datetime.now(),
            source_name=news['source'],
            source_url=news.get('url', ''),
            provider_id=news['provider'],
            language='zh'
        )

    def _parse_datetime(self, dt_str: str) -> datetime:
        """解析日期时间字符串"""
        if not dt_str:
            return datetime.now()

        # 尝试多种格式
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%H:%M:%S",
            "%H:%M"
        ]

        for fmt in formats:
            try:
                return datetime.strptime(dt_str, fmt)
            except ValueError:
                continue

        # 如果都失败，返回当前时间
        logger.warning(f"无法解析日期时间: {dt_str}")
        return datetime.now()


# 全局单例
_global_collector = None


def get_unified_collector() -> UnifiedNewsCollector:
    """获取全局统一采集器（单例模式）"""
    global _global_collector
    if _global_collector is None:
        _global_collector = UnifiedNewsCollector()
        _global_collector.initialize()
    return _global_collector


if __name__ == "__main__":
    import sys
    import io

    # 测试
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )

    # 修复Windows控制台编码
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    collector = get_unified_collector()

    # 测试宏观新闻采集
    print("\n" + "=" * 60)
    print("测试：采集宏观新闻")
    print("=" * 60)
    result = collector.collect_macro_news(limit=10)
    print(f"结果: {result}")

    # 测试个股新闻采集（跳过，因为akshare在Python 3.14不兼容）
    print("\n" + "=" * 60)
    print("测试：采集个股新闻（跳过 - akshare不兼容）")
    print("=" * 60)
    print("个股新闻需要akshare，但Python 3.14不兼容，跳过测试")

    # 健康检查
    print("\n" + "=" * 60)
    print("健康检查")
    print("=" * 60)
    health = collector.health_check()
    for provider, status in health.items():
        print(f"  {provider}: {'[OK]' if status else '[FAIL]'}")
