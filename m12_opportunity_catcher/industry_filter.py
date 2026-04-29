"""
行业过滤器 - 只关注科技类高新产业

关注行业：
  - 游戏
  - 互联网/社交媒体
  - 人工智能/机器学习
  - 云计算/SaaS
  - 半导体/芯片
  - 软件开发
  - 电商/在线服务
  - 网络安全
  - 区块链/加密货币

排除行业：
  - 传统制造业
  - 房地产
  - 金融/银行/保险
  - 能源/石油
  - 零售/超市
  - 餐饮/酒店
  - 交通运输
  - 医药/生物（除非是AI制药）
"""
from __future__ import annotations

import logging
from typing import List, Set

logger = logging.getLogger(__name__)


class IndustryFilter:
    """行业过滤器 - 基于名称关键词和白名单"""

    # 科技类关键词（英文）
    TECH_KEYWORDS_EN = {
        # AI/ML
        'ai', 'artificial intelligence', 'machine learning', 'deep learning',
        'neural', 'openai', 'anthropic', 'nvidia', 'amd',

        # 互联网/社交
        'internet', 'social', 'meta', 'facebook', 'twitter', 'tiktok',
        'bytedance', 'tencent', 'alibaba', 'baidu', 'google', 'alphabet',

        # 游戏
        'game', 'gaming', 'esports', 'unity', 'unreal', 'roblox',
        'activision', 'blizzard', 'riot', 'epic',

        # 云计算/SaaS
        'cloud', 'saas', 'aws', 'azure', 'salesforce', 'servicenow',
        'snowflake', 'datadog', 'mongodb', 'elastic',

        # 半导体/芯片
        'semiconductor', 'chip', 'intel', 'qualcomm', 'broadcom',
        'micron', 'tsmc', 'asml',

        # 软件
        'software', 'microsoft', 'oracle', 'adobe', 'autodesk',
        'atlassian', 'zoom', 'slack', 'notion',

        # 电商
        'ecommerce', 'e-commerce', 'amazon', 'shopify', 'ebay',
        'etsy', 'wayfair', 'chewy',

        # 网络安全
        'cyber', 'security', 'crowdstrike', 'palo alto', 'fortinet',
        'zscaler', 'okta',

        # 区块链/加密
        'blockchain', 'crypto', 'bitcoin', 'ethereum', 'coinbase',

        # 其他科技
        'tech', 'digital', 'online', 'platform', 'data', 'analytics',
    }

    # 科技类关键词（中文）
    TECH_KEYWORDS_CN = {
        # AI/ML
        '人工智能', 'AI', '机器学习', '深度学习', '神经网络',
        '智能', '算法', '大模型',

        # 互联网/社交
        '互联网', '社交', '腾讯', '阿里', '百度', '字节',
        '美团', '拼多多', '京东', '网易', '新浪', '搜狐',

        # 游戏
        '游戏', '电竞', '网游', '手游',

        # 云计算/SaaS
        '云计算', '云服务', 'SaaS', '数据中心',

        # 半导体/芯片
        '半导体', '芯片', '集成电路', 'IC',

        # 软件
        '软件', '信息技术', 'IT',

        # 电商
        '电商', '电子商务', '网购', '在线零售',

        # 网络安全
        '网络安全', '信息安全', '网安',

        # 区块链
        '区块链', '加密', '数字货币',

        # 其他科技
        '科技', '数字', '在线', '平台', '数据',
    }

    # 排除关键词（传统行业）
    EXCLUDE_KEYWORDS = {
        # 英文
        'bank', 'insurance', 'financial', 'realty', 'real estate',
        'oil', 'energy', 'petroleum', 'gas', 'coal',
        'retail', 'supermarket', 'grocery', 'restaurant', 'hotel',
        'airline', 'shipping', 'transport', 'logistics',
        'pharma', 'drug', 'biotech', 'medical', 'hospital',
        'construction', 'building', 'cement', 'steel',

        # 中文
        '银行', '保险', '金融', '地产', '房地产',
        '石油', '能源', '煤炭', '天然气',
        '零售', '超市', '餐饮', '酒店', '旅游',
        '航空', '物流', '运输', '快递',
        '医药', '生物', '制药', '医疗', '医院',
        '建筑', '水泥', '钢铁', '化工',
    }

    # 白名单：知名科技公司（股票代码）
    WHITELIST = {
        # 美股科技巨头
        'AAPL.US', 'MSFT.US', 'GOOGL.US', 'GOOG.US', 'AMZN.US',
        'META.US', 'NVDA.US', 'TSLA.US', 'AMD.US', 'INTC.US',
        'NFLX.US', 'ADBE.US', 'CRM.US', 'ORCL.US', 'CSCO.US',
        'AVGO.US', 'QCOM.US', 'TXN.US', 'AMAT.US', 'MU.US',
        'SNOW.US', 'DDOG.US', 'MDB.US', 'NET.US', 'CRWD.US',
        'ZS.US', 'PANW.US', 'FTNT.US', 'OKTA.US',
        'SHOP.US', 'SQ.US', 'PYPL.US', 'COIN.US',
        'RBLX.US', 'U.US', 'EA.US', 'ATVI.US', 'TTWO.US',

        # A股科技龙头
        '000063.SZ',  # 中兴通讯
        '000725.SZ',  # 京东方A
        '002230.SZ',  # 科大讯飞
        '002415.SZ',  # 海康威视
        '002475.SZ',  # 立讯精密
        '300059.SZ',  # 东方财富
        '300750.SZ',  # 宁德时代
        '600519.SH',  # 贵州茅台（虽然是白酒，但市值大，保留）
        '600570.SH',  # 恒生电子
        '600588.SH',  # 用友网络
        '600745.SH',  # 闻泰科技
        '603160.SH',  # 汇顶科技
        '688012.SH',  # 中微公司
        '688981.SH',  # 中芯国际
    }

    def is_tech_stock(self, symbol: str, name: str = None) -> bool:
        """
        判断是否为科技股

        Args:
            symbol: 股票代码
            name: 股票名称（可选）

        Returns:
            True if 科技股, False otherwise
        """
        # 白名单直接通过
        if symbol in self.WHITELIST:
            return True

        # 如果没有名称，无法判断
        if not name:
            return False

        name_lower = name.lower()

        # 检查排除关键词
        for keyword in self.EXCLUDE_KEYWORDS:
            if keyword.lower() in name_lower:
                return False

        # 检查科技关键词
        for keyword in self.TECH_KEYWORDS_EN:
            if keyword.lower() in name_lower:
                return True

        for keyword in self.TECH_KEYWORDS_CN:
            if keyword in name:
                return True

        # 默认不通过
        return False

    def filter_stock_list(self, stocks: List[tuple]) -> List[str]:
        """
        过滤股票列表，只保留科技股

        Args:
            stocks: [(symbol, name), ...] 股票列表

        Returns:
            科技股代码列表
        """
        tech_stocks = []
        for symbol, name in stocks:
            if self.is_tech_stock(symbol, name):
                tech_stocks.append(symbol)

        logger.info(f"[IndustryFilter] filtered {len(stocks)} -> {len(tech_stocks)} tech stocks")
        return tech_stocks


# 全局单例
_industry_filter = None


def get_industry_filter() -> IndustryFilter:
    """获取全局行业过滤器单例"""
    global _industry_filter
    if _industry_filter is None:
        _industry_filter = IndustryFilter()
    return _industry_filter
