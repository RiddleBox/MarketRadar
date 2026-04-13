"""
m0_collector/providers/akshare_provider.py — AKShare 新闻 Provider

从 AKShare 拉取：
  1. 财经新闻快讯（stock_news_em）
  2. 行业研报摘要（可扩展）
  3. 重要公告（可扩展）

格式化为 RawArticle，经 Normalizer 写入 data/incoming/。
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, date, timedelta
from typing import List, Optional

from m0_collector.models import RawArticle
from m0_collector.providers.base import ProviderAdapter

logger = logging.getLogger(__name__)


class AKShareNewsProvider(ProviderAdapter):
    """
    AKShare 财经新闻 Provider。

    数据源：
      - akshare.stock_news_em()  — 东方财富财经新闻（免费，无需 Token）
      - akshare.stock_zh_a_alerts_cls() — 财联社实时快讯（免费）
    """

    @property
    def provider_id(self) -> str:
        return "akshare_news"

    def fetch(
        self,
        date_filter: Optional[date] = None,
        limit: int = 50,
        source: str = "eastmoney",   # "eastmoney" | "cls" | "all"
        **kwargs,
    ) -> List[RawArticle]:
        """
        拉取财经新闻。

        Args:
            date_filter: 只拉取该日期的新闻，None=最新
            limit:       最大条数
            source:      数据来源

        Returns:
            RawArticle 列表
        """
        articles = []

        if source in ("eastmoney", "all"):
            articles.extend(self._fetch_eastmoney(limit=limit))

        if source in ("cls", "all"):
            articles.extend(self._fetch_cls(limit=limit))

        # 按日期过滤
        if date_filter:
            articles = [a for a in articles if self._parse_date(a.raw_date) == date_filter]

        logger.info(f"[AKShareNewsProvider] 获取 {len(articles)} 条新闻（source={source}）")
        return articles[:limit]

    def _fetch_eastmoney(self, limit: int = 50) -> List[RawArticle]:
        """东方财富财经新闻"""
        try:
            import akshare as ak
            df = ak.stock_news_em(symbol="全部")
            if df is None or df.empty:
                return []

            articles = []
            for _, row in df.head(limit).iterrows():
                title = str(row.get("新闻标题", "") or "").strip()
                content = str(row.get("新闻内容", "") or row.get("摘要", "") or "").strip()
                dt = str(row.get("发布时间", "") or row.get("时间", datetime.now().isoformat()))
                url = str(row.get("新闻链接", "") or "")

                if not title:
                    continue

                articles.append(RawArticle(
                    raw_title=title,
                    raw_content=content or title,
                    raw_date=dt,
                    raw_source="东方财富",
                    raw_url=url,
                    raw_signal_type=self._infer_signal_type(title + content),
                    raw_tags=self._extract_tags(title + content),
                    origin_file=f"akshare_em_{hashlib.md5(url.encode()).hexdigest()[:8]}",
                    editor_notes="",
                    language="zh",
                ))
            return articles

        except ImportError:
            logger.error("[AKShareNewsProvider] 请安装 akshare: pip install akshare")
            return []
        except Exception as e:
            logger.warning(f"[AKShareNewsProvider] 东方财富新闻获取失败: {e}")
            return []

    def _fetch_cls(self, limit: int = 50) -> List[RawArticle]:
        """财联社实时快讯"""
        try:
            import akshare as ak
            df = ak.stock_zh_a_alerts_cls()
            if df is None or df.empty:
                return []

            articles = []
            for _, row in df.head(limit).iterrows():
                title = str(row.get("标题", "") or row.get("内容", "") or "").strip()
                content = str(row.get("内容", "") or title)
                dt = str(row.get("时间", datetime.now().isoformat()))
                url = str(row.get("链接", "") or "")

                if not title:
                    continue

                articles.append(RawArticle(
                    raw_title=title[:200],
                    raw_content=content,
                    raw_date=dt,
                    raw_source="财联社",
                    raw_url=url,
                    raw_signal_type=self._infer_signal_type(title + content),
                    raw_tags=self._extract_tags(title),
                    origin_file=f"akshare_cls_{hashlib.md5((title + dt).encode()).hexdigest()[:8]}",
                    editor_notes="",
                    language="zh",
                ))
            return articles

        except Exception as e:
            logger.warning(f"[AKShareNewsProvider] 财联社快讯获取失败: {e}")
            return []

    # ── 工具函数 ──────────────────────────────────────────────

    MACRO_KEYWORDS = ["GDP", "CPI", "PPI", "PMI", "央行", "利率", "降息", "加息",
                      "货币政策", "财政政策", "经济数据", "通胀", "就业", "美联储", "联储"]
    POLICY_KEYWORDS = ["政策", "政府", "国务院", "证监会", "银保监", "监管", "新规",
                       "指引", "通知", "意见", "改革", "刺激", "补贴"]
    CAPITAL_KEYWORDS = ["北向资金", "南向资金", "主力", "外资", "资金流", "融资",
                        "净流入", "净流出", "QFII", "陆股通", "港股通"]
    INDUSTRY_KEYWORDS = ["行业", "板块", "赛道", "新能源", "半导体", "医药", "消费",
                         "地产", "银行", "科技", "军工", "光伏", "电池", "AI"]
    TECH_KEYWORDS = ["技术面", "突破", "支撑", "压力", "均线", "MACD", "KDJ",
                     "RSI", "成交量", "换手率", "涨停", "跌停"]

    def _infer_signal_type(self, text: str) -> str:
        text_lower = text.lower()
        if any(k in text for k in self.CAPITAL_KEYWORDS):
            return "capital_flow"
        if any(k in text for k in self.MACRO_KEYWORDS):
            return "macro"
        if any(k in text for k in self.POLICY_KEYWORDS):
            return "policy"
        if any(k in text for k in self.INDUSTRY_KEYWORDS):
            return "industry"
        if any(k in text for k in self.TECH_KEYWORDS):
            return "technical"
        return "event_driven"

    def _extract_tags(self, text: str) -> List[str]:
        tags = []
        for kw in self.MACRO_KEYWORDS + self.POLICY_KEYWORDS + self.INDUSTRY_KEYWORDS:
            if kw in text and kw not in tags:
                tags.append(kw)
        return tags[:5]

    def _parse_date(self, raw_date: str) -> Optional[date]:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
                    "%Y/%m/%d %H:%M:%S", "%Y/%m/%d"):
            try:
                return datetime.strptime(raw_date[:len(fmt)], fmt).date()
            except Exception:
                pass
        return None
