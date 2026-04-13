"""
m0_collector/providers/sentiment_provider.py — 情绪面数据采集 Provider

数据来源（全部通过 AKShare 获取，无需额外 API Key）：
  1. 股票综合评分 (stock_comment_em)       — 东方财富个股综合得分 + 关注指数
  2. 百度热搜 (stock_hot_search_baidu)     — 市场热搜热度分布
  3. 北向资金 (stock_hsgt_fund_flow_summary_em) — 外资情绪晴雨表
  4. 微博情绪 (stock_js_weibo_report)      — 社交媒体提及股票的情绪 rate
  5. 东财热股计数 (stock_hot_rank_latest_em) — 全市场热度统计

输出：SentimentSnapshot（单次快照）→ 可转换为 MarketSignal 注入 M2
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class SentimentSnapshot:
    """
    情绪面快照 — 一次采集的所有原始情绪数据。

    分为四个维度：
      - market_breadth:  市场宽度（涨跌家数/热股数量）
      - capital_flow:    资金面（北向净流入）
      - social_heat:     社交热度（百度热搜/微博情绪）
      - stock_scores:    个股评分样本（综合得分分布）
    """
    snapshot_time: datetime = field(default_factory=datetime.now)
    source: str = "akshare"

    # 市场宽度
    market_total_stocks: int = 0      # 全市场总标的数
    market_up_count: int = 0          # 上涨家数（北向）
    market_down_count: int = 0        # 下跌家数
    advance_decline_ratio: float = 0.0  # 涨跌比 = up / (up + down)

    # 资金面（北向）
    northbound_net_flow: float = 0.0    # 北向净流入（亿元）；负=净流出
    southbound_net_flow: float = 0.0    # 南向净流入

    # 社交热度
    baidu_hot_stocks: List[Tuple[str, float]] = field(default_factory=list)
    # [(股票名, 热度值), ...]
    weibo_sentiment_stocks: List[Tuple[str, float]] = field(default_factory=list)
    # [(股票名, 情绪 rate), ...] rate>0 看多，<0 看空

    # 个股评分分布（来自 stock_comment_em 抽样）
    avg_comprehensive_score: float = 50.0  # 均综合得分（0-100）
    avg_attention_index: float = 50.0      # 均关注指数
    high_score_count: int = 0              # 综合得分 > 70 的标的数
    low_score_count: int = 0               # 综合得分 < 30 的标的数

    # 采集元数据
    errors: List[str] = field(default_factory=list)
    partial: bool = False  # True = 部分指标采集失败

    def fear_greed_score(self) -> float:
        """
        综合情绪得分：0（极度恐惧）~ 100（极度贪婪）。

        加权计算：
          - 涨跌比 (35%):      market_up/down 或 advance_decline_ratio
          - 北向资金 (30%):    northbound_net_flow 归一化
          - 个股评分 (25%):    avg_comprehensive_score
          - 社交热度 (10%):    微博情绪 rate 均值
        """
        components = []  # [(score_0_100, weight)]

        # 1. 涨跌比 (35%)
        if self.market_up_count + self.market_down_count > 0:
            adr = self.market_up_count / (self.market_up_count + self.market_down_count)
            components.append((adr * 100, 0.35))
        elif self.advance_decline_ratio > 0:
            components.append((self.advance_decline_ratio * 100, 0.35))

        # 2. 北向资金 (30%)
        flow = self.northbound_net_flow
        if flow != 0.0:
            # 线性映射：-200亿→0, 0→50, +200亿→100
            clamped = max(-200, min(200, flow))
            score_flow = 50 + (clamped / 200) * 50
            components.append((score_flow, 0.30))

        # 3. 个股综合评分 (25%) — 原始值已是 0~100
        if self.avg_comprehensive_score > 0:
            components.append((self.avg_comprehensive_score, 0.25))

        # 4. 微博情绪均值 (10%) — rate 范围 -1~1 → 0~100
        if self.weibo_sentiment_stocks:
            rates = [r for _, r in self.weibo_sentiment_stocks]
            mean_rate = sum(rates) / len(rates)
            score_weibo = 50 + mean_rate * 50  # 1.0→100, -1.0→0
            components.append((score_weibo, 0.10))

        if not components:
            return 50.0

        # 加权平均
        total_weight = sum(w for _, w in components)
        weighted_sum = sum(s * w for s, w in components)
        return max(0.0, min(100.0, weighted_sum / total_weight))

    def sentiment_label(self) -> str:
        """将 fear_greed_score 转换为文字标签"""
        s = self.fear_greed_score()
        if s >= 80:   return "极度贪婪"
        if s >= 65:   return "贪婪"
        if s >= 55:   return "略偏乐观"
        if s >= 45:   return "中性"
        if s >= 35:   return "略偏谨慎"
        if s >= 20:   return "恐惧"
        return "极度恐惧"

    def direction(self) -> str:
        """情绪方向"""
        s = self.fear_greed_score()
        if s >= 60:  return "BULLISH"
        if s <= 40:  return "BEARISH"
        return "NEUTRAL"

    def hot_sectors(self) -> List[str]:
        """从百度热搜和微博情绪中提取热门标的"""
        result = []
        for name, heat in sorted(self.baidu_hot_stocks, key=lambda x: -x[1])[:5]:
            result.append(name)
        return result


class SentimentProvider:
    """
    情绪面数据采集 Provider。

    从 AKShare 采集多个维度的情绪数据，汇总为 SentimentSnapshot。
    单次调用 fetch() 即可获取完整快照。

    失败容忍：任何单个数据源失败都不会阻断整体采集。
    """

    def fetch(self) -> SentimentSnapshot:
        """采集完整情绪快照（约 5-10 秒）"""
        snap = SentimentSnapshot()

        self._fetch_northbound(snap)
        self._fetch_comment_scores(snap)
        self._fetch_baidu_hot(snap)
        self._fetch_weibo_sentiment(snap)

        snap.partial = len(snap.errors) > 0
        return snap

    def _fetch_northbound(self, snap: SentimentSnapshot):
        """北向资金净流入"""
        try:
            import akshare as ak
            df = ak.stock_hsgt_fund_flow_summary_em()
            # 过滤北向（沪股通+深股通）
            north = df[df["资金方向"] == "北向"]
            if not north.empty:
                total_net = float(north["资金净流入"].sum())
                snap.northbound_net_flow = round(total_net, 2)
                # 涨跌家数
                up = int(north["上涨数"].sum())
                down = int(north["下跌数"].sum())
                snap.market_up_count = up
                snap.market_down_count = down
                if up + down > 0:
                    snap.advance_decline_ratio = round(up / (up + down), 4)
            # 南向
            south = df[df["资金方向"] == "南向"]
            if not south.empty:
                snap.southbound_net_flow = round(float(south["资金净流入"].sum()), 2)
            logger.debug(f"[Sentiment] 北向净流入: {snap.northbound_net_flow}亿")
        except Exception as e:
            snap.errors.append(f"northbound: {e}")
            logger.warning(f"[Sentiment] 北向资金采集失败: {e}")

    def _fetch_comment_scores(self, snap: SentimentSnapshot):
        """个股综合评分分布（取前 200 名）"""
        try:
            import akshare as ak
            df = ak.stock_comment_em()
            if df.empty:
                return
            scores = df["综合得分"].dropna()
            attentions = df["关注指数"].dropna()
            snap.avg_comprehensive_score = round(float(scores.mean()), 2)
            snap.avg_attention_index = round(float(attentions.mean()), 2)
            snap.high_score_count = int((scores > 70).sum())
            snap.low_score_count = int((scores < 30).sum())
            snap.market_total_stocks = len(df)
            logger.debug(f"[Sentiment] 均综合得分: {snap.avg_comprehensive_score}")
        except Exception as e:
            snap.errors.append(f"comment_scores: {e}")
            logger.warning(f"[Sentiment] 个股评分采集失败: {e}")

    def _fetch_baidu_hot(self, snap: SentimentSnapshot):
        """百度热搜股票"""
        try:
            import akshare as ak
            df = ak.stock_hot_search_baidu()
            if df.empty:
                return
            result = []
            for _, row in df.iterrows():
                name = str(row.get("名称/代码", ""))
                heat = float(row.get("综合热度", 0) or 0)
                result.append((name, heat))
            snap.baidu_hot_stocks = result[:10]  # 取前10
            logger.debug(f"[Sentiment] 百度热搜: {[n for n,_ in result[:3]]}")
        except Exception as e:
            snap.errors.append(f"baidu_hot: {e}")
            logger.warning(f"[Sentiment] 百度热搜采集失败: {e}")

    def _fetch_weibo_sentiment(self, snap: SentimentSnapshot):
        """微博提及股票情绪 rate"""
        try:
            import akshare as ak
            df = ak.stock_js_weibo_report()
            if df.empty:
                return
            result = []
            for _, row in df.iterrows():
                name = str(row.get("name", ""))
                rate = float(row.get("rate", 0) or 0)
                result.append((name, rate))
            snap.weibo_sentiment_stocks = result[:20]
            logger.debug(f"[Sentiment] 微博情绪采集: {len(result)} 条")
        except Exception as e:
            snap.errors.append(f"weibo_sentiment: {e}")
            logger.warning(f"[Sentiment] 微博情绪采集失败: {e}")
