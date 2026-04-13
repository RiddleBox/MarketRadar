"""m0_collector package"""
from m0_collector.providers.rss import RssProvider
from m0_collector.providers.manual import ManualProvider

__all__ = ["RssProvider", "ManualProvider"]
