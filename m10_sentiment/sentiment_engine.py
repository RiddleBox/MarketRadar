"""
m10_sentiment/sentiment_engine.py — 情绪面合成引擎

职责：
  1. 调用 SentimentProvider 采集原始数据
  2. 合成 FearGreed 指数（0~100）
  3. 生成结构化 SentimentSignal（兼容 MarketSignal，可注入 M2）
  4. 检测情绪极值（反转信号）
  5. 检测情绪共振（与宏观/政策信号叠加时放大）

情绪信号类型（signal_type='sentiment'）会在 M3 机会判断中作为辅助输入：
  - 极度贪婪(>80) + 上涨信号 → 可能已经过热，谨慎入场
  - 极度恐惧(<20) + 政策信号 → 恐慌底部 + 政策催化，强买入信号
  - 贪婪区间(60~80) + 资金流入 → 情绪共振，顺势加仓
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent


class SentimentEngine:
    """
    情绪面合成引擎。

    调用链：
        SentimentProvider.fetch() → SentimentSnapshot
        → compute_fear_greed()       → float (0~100)
        → generate_signal()          → SentimentSignalData
        → inject_to_m2()             → MarketSignal (存 M2)
    """

    def __init__(self):
        from m0_collector.providers.sentiment_provider import SentimentProvider
        self.provider = SentimentProvider()

    def run(self, batch_id: str = "", save_snapshot: bool = True) -> Optional[object]:
        """
        完整运行一次情绪面采集 + 信号生成。

        Returns:
            SentimentSignalData（可直接注入 M2）或 None（采集失败）
        """
        if not batch_id:
            batch_id = f"sentiment_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        logger.info(f"[SentimentEngine] 开始采集情绪数据 batch={batch_id}")
        snap = self.provider.fetch()

        if snap.partial:
            logger.warning(f"[SentimentEngine] 部分指标失败: {snap.errors}")

        score = snap.fear_greed_score()
        label = snap.sentiment_label()
        direction = snap.direction()
        hot = snap.hot_sectors()

        logger.info(
            f"[SentimentEngine] 情绪指数: {score:.1f} ({label}) "
            f"| 北向: {snap.northbound_net_flow:+.1f}亿 "
            f"| 涨跌比: {snap.advance_decline_ratio:.2f}"
        )

        # 检测情绪极值（反转信号）
        is_extreme = score >= 80 or score <= 20

        # 构建情绪信号
        from integrations.market_sentinel import SentimentSignalData
        signal = SentimentSignalData(
            signal_id=f"sent_{uuid.uuid4().hex[:12]}",
            signal_type="sentiment",
            signal_label=f"市场情绪: {label}（恐贪指数 {score:.0f}）",
            description=self._build_description(snap, score, label),
            evidence_text=self._build_evidence(snap),
            affected_markets=["A_SHARE"],
            affected_instruments=hot[:3],
            signal_direction=direction,
            fear_greed_index=score,
            sentiment_label=label,
            hot_sectors=hot,
            rotating_to=hot[:2],
            intensity_score=self._compute_intensity(score),
            confidence_score=self._compute_confidence(snap),
            timeliness_score=9.0,
            event_time=snap.snapshot_time,
            batch_id=batch_id,
        )

        if save_snapshot:
            self._save_snapshot(snap, signal, batch_id)

        return signal

    def run_and_inject(self, batch_id: str = "") -> Optional[object]:
        """运行采集 + 注入 M2 + 返回信号"""
        signal = self.run(batch_id=batch_id)
        if signal is None:
            return None

        try:
            from m2_storage.signal_store import SignalStore
            from core.schemas import MarketSignal
            ms = MarketSignal(**signal.to_market_signal_dict())
            store = SignalStore()
            store.save([ms])
            logger.info(f"[SentimentEngine] 情绪信号已注入 M2: {signal.signal_id}")
        except Exception as e:
            logger.error(f"[SentimentEngine] 注入 M2 失败: {e}")

        return signal

    # ── 内部计算方法 ─────────────────────────────────────────

    def _compute_intensity(self, score: float) -> float:
        """
        情绪强度 (1~10)：
          - 极值区间（<20 或 >80）→ 高强度（8~10）
          - 中性区间（40~60）→ 低强度（2~4）
        """
        deviation = abs(score - 50)  # 0~50
        return round(2.0 + (deviation / 50) * 8.0, 1)

    def _compute_confidence(self, snap) -> float:
        """
        置信度 (1~10)：基于成功采集的指标数量。
        """
        total_sources = 4  # northbound, scores, baidu, weibo
        failed = len(snap.errors)
        success_rate = (total_sources - failed) / total_sources
        return round(5.0 + success_rate * 4.0, 1)

    def _build_description(self, snap, score: float, label: str) -> str:
        lines = [
            f"【市场情绪面快照】",
            f"恐贪指数: {score:.1f}/100 — {label}",
            f"北向资金净流入: {snap.northbound_net_flow:+.1f}亿元",
            f"涨跌家数: 涨{snap.market_up_count}/跌{snap.market_down_count}",
            f"  涨跌比: {snap.advance_decline_ratio:.2%}",
            f"个股均综合评分: {snap.avg_comprehensive_score:.1f}/100",
            f"高分股数量(>70分): {snap.high_score_count}",
        ]
        if snap.baidu_hot_stocks:
            top3 = "、".join(n for n, _ in snap.baidu_hot_stocks[:3])
            lines.append(f"百度热搜前三: {top3}")
        if snap.weibo_sentiment_stocks:
            pos = sum(1 for _, r in snap.weibo_sentiment_stocks if r > 0)
            neg = sum(1 for _, r in snap.weibo_sentiment_stocks if r < 0)
            lines.append(f"微博情绪: 正面{pos}条/负面{neg}条")
        return "\n".join(lines)

    def _build_evidence(self, snap) -> str:
        parts = []
        if snap.northbound_net_flow != 0:
            parts.append(f"北向净流入{snap.northbound_net_flow:+.1f}亿")
        if snap.baidu_hot_stocks:
            parts.append(f"百度热搜: {snap.baidu_hot_stocks[0][0]}热度{snap.baidu_hot_stocks[0][1]:.0f}")
        if snap.avg_comprehensive_score:
            parts.append(f"均综合得分{snap.avg_comprehensive_score:.1f}")
        return "；".join(parts) or "情绪数据采集中"

    def _save_snapshot(self, snap, signal, batch_id: str):
        """保存原始快照到 data/sentiment/"""
        try:
            out_dir = ROOT / "data" / "sentiment"
            out_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_file = out_dir / f"snapshot_{ts}.json"
            data = {
                "batch_id": batch_id,
                "snapshot_time": snap.snapshot_time.isoformat(),
                "fear_greed_score": signal.fear_greed_index,
                "sentiment_label": signal.sentiment_label,
                "direction": signal.signal_direction,
                "northbound_net_flow": snap.northbound_net_flow,
                "advance_decline_ratio": snap.advance_decline_ratio,
                "avg_comprehensive_score": snap.avg_comprehensive_score,
                "high_score_count": snap.high_score_count,
                "baidu_hot_stocks": snap.baidu_hot_stocks[:5],
                "weibo_sentiment": snap.weibo_sentiment_stocks[:10],
                "errors": snap.errors,
                "partial": snap.partial,
            }
            out_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info(f"[SentimentEngine] 快照已保存: {out_file.name}")
        except Exception as e:
            logger.warning(f"[SentimentEngine] 快照保存失败: {e}")

    # ── 情绪历史读取 ─────────────────────────────────────────

    def load_history(self, last_n: int = 10) -> list:
        """读取最近 N 次情绪快照"""
        out_dir = ROOT / "data" / "sentiment"
        if not out_dir.exists():
            return []
        files = sorted(out_dir.glob("snapshot_*.json"), reverse=True)[:last_n]
        result = []
        for f in files:
            try:
                result.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                pass
        return result

    def latest_snapshot(self) -> Optional[dict]:
        """返回最新一次快照"""
        history = self.load_history(1)
        return history[0] if history else None
