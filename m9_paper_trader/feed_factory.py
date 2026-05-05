"""
数据源工厂 - 统一管理所有价格数据源的创建和配置
"""
import yaml
from pathlib import Path
from typing import Optional, Dict, Any
from loguru import logger

from core.schemas import Market
from m9_paper_trader.price_feed import PriceFeed


class DataFeedFactory:
    """数据源工厂，根据配置文件创建对应的PriceFeed实例"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化数据源工厂
        
        Args:
            config_path: 配置文件路径，默认为 config/data_sources.yaml
        """
        if config_path is None:
            # 默认配置文件路径
            repo_root = Path(__file__).parent.parent
            config_path = repo_root / "config" / "data_sources.yaml"
        
        self.config_path = Path(config_path)
        self.config = self._load_config()
        
        # 缓存已创建的feed实例（避免重复创建连接）
        self._feed_cache: Dict[str, PriceFeed] = {}
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            logger.info(f"[DataFeedFactory] 加载配置: {self.config_path}")
            return config
        except Exception as e:
            logger.error(f"[DataFeedFactory] 配置加载失败: {e}")
            # 返回默认配置
            return {
                "primary": {
                    "a_share": "futu",
                    "hk_share": "futu",
                    "us_share": "futu"
                },
                "fallback": {
                    "a_share": "akshare",
                    "hk_share": "yfinance",
                    "us_share": "yfinance"
                }
            }
    
    def _create_feed_instance(self, feed_type: str) -> PriceFeed:
        """
        创建数据源实例
        
        Args:
            feed_type: 数据源类型 (futu/baostock/akshare/yfinance)
        
        Returns:
            PriceFeed实例
        """
        feed_type = feed_type.lower()
        
        # 检查缓存
        if feed_type in self._feed_cache:
            return self._feed_cache[feed_type]
        
        # 创建新实例
        try:
            if feed_type == "futu":
                from m9_paper_trader.futu_feed import FutuFeed
                feed = FutuFeed()
                logger.info("[DataFeedFactory] 创建 FutuFeed")
            
            elif feed_type == "baostock":
                from m9_paper_trader.baostock_feed import BaostockFeed
                feed = BaostockFeed()
                logger.info("[DataFeedFactory] 创建 BaostockFeed")
            
            elif feed_type == "akshare":
                from m9_paper_trader.price_feed import AKShareRealtimeFeed
                feed = AKShareRealtimeFeed()
                logger.info("[DataFeedFactory] 创建 AKShareRealtimeFeed")
            
            elif feed_type == "yfinance":
                from m9_paper_trader.price_feed import YFinanceFeed
                feed = YFinanceFeed()
                logger.info("[DataFeedFactory] 创建 YFinanceFeed")
            
            else:
                logger.error(f"[DataFeedFactory] 未知数据源类型: {feed_type}")
                # 默认返回AKShare
                from m9_paper_trader.price_feed import AKShareRealtimeFeed
                feed = AKShareRealtimeFeed()
            
            # 缓存实例
            self._feed_cache[feed_type] = feed
            return feed
        
        except Exception as e:
            logger.error(f"[DataFeedFactory] 创建 {feed_type} 失败: {e}")
            # 降级到AKShare
            from m9_paper_trader.price_feed import AKShareRealtimeFeed
            return AKShareRealtimeFeed()
    
    def get_feed(
        self,
        market: Market,
        scenario: Optional[str] = None,
        use_fallback: bool = False
    ) -> PriceFeed:
        """
        获取指定市场的数据源
        
        Args:
            market: 市场类型
            scenario: 场景名称（如 m7_premarket_scan），为None时使用primary配置
            use_fallback: 是否使用备用数据源
        
        Returns:
            PriceFeed实例
        """
        # 确定市场配置键
        if market == Market.A_SHARE:
            market_key = "a_share"
        elif market == Market.HK:
            market_key = "hk_share"
        elif market == Market.US:
            market_key = "us_share"
        else:
            logger.warning(f"[DataFeedFactory] 未知市场: {market}")
            market_key = "a_share"
        
        # 确定数据源类型
        if scenario and scenario in self.config.get("scenarios", {}):
            # 使用场景配置
            feed_type = self.config["scenarios"][scenario].get(market_key)
            logger.info(f"[DataFeedFactory] 场景 {scenario} | {market_key} -> {feed_type}")
        elif use_fallback:
            # 使用备用配置
            feed_type = self.config["fallback"].get(market_key)
            logger.info(f"[DataFeedFactory] 备用数据源 | {market_key} -> {feed_type}")
        else:
            # 使用主配置
            feed_type = self.config["primary"].get(market_key)
            logger.info(f"[DataFeedFactory] 主数据源 | {market_key} -> {feed_type}")
        
        if not feed_type:
            logger.error(f"[DataFeedFactory] 未找到配置: market={market_key}, scenario={scenario}")
            feed_type = "akshare"  # 默认
        
        return self._create_feed_instance(feed_type)
    
    def get_feed_with_fallback(
        self,
        market: Market,
        scenario: Optional[str] = None
    ) -> PriceFeed:
        """
        获取数据源，失败时自动降级到备用数据源
        
        Args:
            market: 市场类型
            scenario: 场景名称
        
        Returns:
            PriceFeed实例
        """
        try:
            # 先尝试主数据源
            feed = self.get_feed(market, scenario, use_fallback=False)
            
            # 检查连接状态（仅对FutuFeed）
            if hasattr(feed, 'is_connected') and not feed.is_connected():
                logger.warning(f"[DataFeedFactory] 主数据源未连接，降级到备用")
                return self.get_feed(market, scenario, use_fallback=True)
            
            return feed
        
        except Exception as e:
            logger.error(f"[DataFeedFactory] 主数据源失败: {e}，降级到备用")
            return self.get_feed(market, scenario, use_fallback=True)
    
    def get_m9_price_update_feed(self) -> PriceFeed:
        """
        获取M9模拟盘价格更新专用数据源
        
        Returns:
            PriceFeed实例（优先FutuFeed，失败时降级到AKShare）
        """
        scenario_config = self.config.get("scenarios", {}).get("m9_price_update", {})
        primary_type = scenario_config.get("primary", "futu")
        fallback_type = scenario_config.get("fallback", "akshare")
        
        try:
            feed = self._create_feed_instance(primary_type)
            
            # 检查FutuFeed连接状态
            if hasattr(feed, 'is_connected') and not feed.is_connected():
                logger.warning(f"[DataFeedFactory] {primary_type} 未连接，降级到 {fallback_type}")
                return self._create_feed_instance(fallback_type)
            
            return feed
        
        except Exception as e:
            logger.error(f"[DataFeedFactory] {primary_type} 失败: {e}，降级到 {fallback_type}")
            return self._create_feed_instance(fallback_type)


# 全局单例
_factory_instance: Optional[DataFeedFactory] = None


def get_factory() -> DataFeedFactory:
    """获取全局数据源工厂单例"""
    global _factory_instance
    if _factory_instance is None:
        _factory_instance = DataFeedFactory()
    return _factory_instance
