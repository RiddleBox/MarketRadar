"""
backtest/history_collector.py — 历史数据归集

用 AKShare 批量拉取过去 N 天的财经新闻，
格式化后写入 data/incoming/ 供 M1→M3 链路消费。

特点：
  - 按日期分批拉取，自动去重
  - 支持多来源（东方财富 + 财联社 + 个股公告）
  - 生成 CollectedItem 并写入 txt 文件（与 pipeline/ingest.py 兼容）
"""
from __future__ import annotations

import logging
import hashlib
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

INCOMING_DIR = Path(__file__).parent.parent / "data" / "incoming"


class HistoryCollector:
    """历史新闻归集器"""

    def __init__(self, incoming_dir: Path = INCOMING_DIR):
        self.incoming_dir = incoming_dir
        self.incoming_dir.mkdir(parents=True, exist_ok=True)
        self._seen_urls: set = set()   # 运行期去重（不依赖 DedupIndex）

    def collect_date_range(
        self,
        start: date,
        end: date,
        sources: List[str] = None,
        limit_per_day: int = 100,
    ) -> dict:
        """
        批量拉取 [start, end] 日期范围内的新闻。

        Args:
            start:          开始日期（含）
            end:            结束日期（含）
            sources:        来源列表 ["eastmoney", "cls"]，None=全部
            limit_per_day:  每日每来源最大条数

        Returns:
            {"days": int, "total": int, "files": List[Path], "errors": List[str]}
        """
        sources = sources or ["eastmoney", "cls"]
        all_files: List[Path] = []
        errors: List[str] = []
        days = 0

        cur = start
        while cur <= end:
            day_files, day_errors = self._collect_one_day(cur, sources, limit_per_day)
            all_files.extend(day_files)
            errors.extend(day_errors)
            days += 1
            cur += timedelta(days=1)

        result = {
            "days": days,
            "total": len(all_files),
            "files": all_files,
            "errors": errors,
        }
        logger.info(
            f"[HistoryCollector] 归集完成 | "
            f"{start}→{end} | {days}天 | {len(all_files)}条 | "
            f"错误{len(errors)}个"
        )
        return result

    def _collect_one_day(
        self,
        dt: date,
        sources: List[str],
        limit: int,
    ) -> tuple:
        """归集单日新闻"""
        files = []
        errors = []

        for source in sources:
            try:
                articles = self._fetch_by_source(source, dt, limit)
                for art in articles:
                    f = self._save_article(art, dt, source)
                    if f:
                        files.append(f)
            except Exception as e:
                msg = f"{dt} {source}: {e}"
                logger.warning(f"[HistoryCollector] {msg}")
                errors.append(msg)

        return files, errors

    def _fetch_by_source(self, source: str, dt: date, limit: int) -> List[dict]:
        """从指定来源拉取指定日期的新闻（返回 dict 列表）"""
        try:
            import akshare as ak
        except ImportError:
            logger.error("请先安装 akshare: pip install akshare")
            return []

        articles = []
        dt_str = dt.strftime("%Y-%m-%d")

        if source == "eastmoney":
            try:
                df = ak.stock_news_em(symbol="全部")
                if df is None or df.empty:
                    return []
                # 按日期过滤
                for _, row in df.iterrows():
                    pub_time = str(row.get("发布时间", "") or "")
                    if not pub_time.startswith(dt_str):
                        continue
                    title = str(row.get("新闻标题", "") or "").strip()
                    content = str(row.get("新闻内容", "") or "").strip()
                    url = str(row.get("新闻链接", "") or "")
                    if not title or url in self._seen_urls:
                        continue
                    self._seen_urls.add(url)
                    articles.append({
                        "title": title,
                        "content": content or title,
                        "published_at": pub_time,
                        "source": "东方财富",
                        "url": url,
                        "signal_type": self._infer_type(title + content),
                    })
                    if len(articles) >= limit:
                        break
            except Exception as e:
                logger.warning(f"[HistoryCollector] 东方财富 {dt}: {e}")

        elif source == "cls":
            try:
                df = ak.stock_zh_a_alerts_cls()
                if df is None or df.empty:
                    return []
                for _, row in df.iterrows():
                    pub_time = str(row.get("时间", "") or "")
                    if not pub_time.startswith(dt_str):
                        continue
                    title = str(row.get("标题", "") or row.get("内容", "") or "").strip()
                    content = str(row.get("内容", "") or title)
                    url = str(row.get("链接", "") or "")
                    key = url or hashlib.md5((title + pub_time).encode()).hexdigest()
                    if not title or key in self._seen_urls:
                        continue
                    self._seen_urls.add(key)
                    articles.append({
                        "title": title[:200],
                        "content": content,
                        "published_at": pub_time,
                        "source": "财联社",
                        "url": url,
                        "signal_type": self._infer_type(title + content),
                    })
                    if len(articles) >= limit:
                        break
            except Exception as e:
                logger.warning(f"[HistoryCollector] 财联社 {dt}: {e}")

        return articles

    def _save_article(self, art: dict, dt: date, source: str) -> Optional[Path]:
        """将单条新闻写入 data/incoming/"""
        title = art.get("title", "").strip()
        content = art.get("content", "").strip()
        if not title or len(content) < 10:
            return None

        url = art.get("url", "")
        item_id = hashlib.md5((url or title + str(dt)).encode()).hexdigest()[:8]
        filename = f"{dt.strftime('%Y%m%d')}_{source}_{item_id}.txt"
        path = self.incoming_dir / filename

        if path.exists():
            return None  # 已存在，跳过

        pub_time = art.get("published_at", dt.isoformat())
        src_name = art.get("source", source)
        signal_type = art.get("signal_type", "event_driven")

        text = (
            f"【{src_name}】{title}\n\n"
            f"<!-- source: {src_name} | url: {url} | "
            f"published: {pub_time} | signal_type_hint: {signal_type} -->\n\n"
            f"{content}"
        )
        path.write_text(text, encoding="utf-8")
        return path

    # ── 工具 ────────────────────────────────────────────────

    _MACRO = ["GDP", "CPI", "PPI", "PMI", "央行", "利率", "降息", "加息",
              "货币政策", "美联储", "通胀", "就业", "经济"]
    _POLICY = ["政策", "国务院", "证监会", "监管", "新规", "改革", "刺激"]
    _CAPITAL = ["北向资金", "南向", "主力", "外资", "净流入", "净流出", "融资"]
    _INDUSTRY = ["行业", "板块", "新能源", "半导体", "医药", "消费", "地产", "银行", "科技"]

    def _infer_type(self, text: str) -> str:
        if any(k in text for k in self._CAPITAL):
            return "capital_flow"
        if any(k in text for k in self._MACRO):
            return "macro"
        if any(k in text for k in self._POLICY):
            return "policy"
        if any(k in text for k in self._INDUSTRY):
            return "industry"
        return "event_driven"
