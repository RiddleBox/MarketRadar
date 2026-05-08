"""
数据提供者初始化脚本

从配置文件加载并注册所有数据提供者到全局 DataProviderManager。
在系统启动时调用 initialize_data_providers() 即可完成初始化。
"""

import yaml
import logging
from pathlib import Path
from integrations.data_provider_manager import get_global_data_manager
from integrations.providers import AStockSkillProvider, RSSProvider

logger = logging.getLogger(__name__)


def load_config(config_path: str = "config/data_providers.yaml") -> dict:
    """加载数据提供者配置文件"""
    config_file = Path(config_path)
    if not config_file.exists():
        logger.error(f"配置文件不存在: {config_path}")
        return {}

    with open(config_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    return config


def initialize_data_providers(config_path: str = "config/data_providers.yaml") -> bool:
    """
    初始化所有数据提供者

    Args:
        config_path: 配置文件路径

    Returns:
        True: 初始化成功
        False: 初始化失败
    """
    logger.info("=" * 60)
    logger.info("开始初始化数据提供者...")
    logger.info("=" * 60)

    # 1. 加载配置
    config = load_config(config_path)
    if not config:
        logger.error("配置文件加载失败")
        return False

    providers_config = config.get("providers", {})
    manager = get_global_data_manager()

    success_count = 0
    fail_count = 0

    # 2. 注册 A-stock SKILL Provider
    astock_config = providers_config.get("astock_skill", {})
    if astock_config.get("enabled", False):
        try:
            provider = AStockSkillProvider()
            priority = astock_config.get("priority", 100)
            manager.register_provider("astock_skill", provider, priority)
            success_count += 1
            logger.info(f"✅ A-stock SKILL Provider 注册成功 (优先级: {priority})")
        except Exception as e:
            fail_count += 1
            logger.error(f"❌ A-stock SKILL Provider 注册失败: {e}")
    else:
        logger.info("⏭️  A-stock SKILL Provider 已禁用")

    # 3. 注册 RSS Provider
    rss_config = providers_config.get("rss", {})
    if rss_config.get("enabled", False):
        try:
            feeds = rss_config.get("config", {}).get("feeds", [])
            provider = RSSProvider(feeds=feeds)
            priority = rss_config.get("priority", 60)
            manager.register_provider("rss", provider, priority)
            success_count += 1
            logger.info(f"✅ RSS Provider 注册成功 (优先级: {priority}, {len(feeds)} 个RSS源)")
        except Exception as e:
            fail_count += 1
            logger.error(f"❌ RSS Provider 注册失败: {e}")
    else:
        logger.info("⏭️  RSS Provider 已禁用")

    # 4. AKShare Provider（已禁用，Python 3.14不兼容）
    akshare_config = providers_config.get("akshare", {})
    if akshare_config.get("enabled", False):
        logger.warning("⚠️  AKShare Provider 已在配置中启用，但Python 3.14不兼容，跳过注册")
    else:
        logger.info("⏭️  AKShare Provider 已禁用（Python 3.14不兼容）")

    # 5. 输出初始化结果
    logger.info("=" * 60)
    logger.info(f"数据提供者初始化完成: 成功 {success_count} 个, 失败 {fail_count} 个")
    logger.info("=" * 60)

    # 6. 列出所有能力
    capabilities = manager.list_capabilities()
    logger.info("📋 可用能力列表:")
    for cap, providers in capabilities.items():
        logger.info(f"  - {cap}: {', '.join(providers)}")

    # 7. 健康检查
    logger.info("\n🏥 执行健康检查...")
    health_status = manager.health_check()
    healthy_count = sum(1 for v in health_status.values() if v)
    logger.info(f"健康检查完成: {healthy_count}/{len(health_status)} 个提供者正常")

    return success_count > 0


if __name__ == "__main__":
    import sys
    import io

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 修复Windows控制台编码问题
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    # 初始化
    success = initialize_data_providers()
    if success:
        print("\n[OK] 数据提供者初始化成功")

        # 测试获取新闻
        manager = get_global_data_manager()
        print("\n" + "=" * 60)
        print("测试：获取宏观新闻（多源聚合）")
        print("=" * 60)
        news = manager.get_news(symbol=None, limit=5, aggregate=True)
        print(f"获取到 {len(news)} 条新闻:")
        for i, n in enumerate(news, 1):
            print(f"{i}. [{n['source']}] {n['title'][:50]}... ({n['published_at']})")

        print("\n" + "=" * 60)
        print("测试：获取个股行情")
        print("=" * 60)
        quote = manager.get_quote("000001")
        if quote:
            print(f"平安银行(000001): 价格={quote.get('price')}, PE={quote.get('pe_ttm')}, PB={quote.get('pb')}")
        else:
            print("获取行情失败")

    else:
        print("\n[ERROR] 数据提供者初始化失败")
