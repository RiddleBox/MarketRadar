"""
m3_judgment/sentiment_resonance.py — M3 情绪共振逻辑

设计原则（来自 docs/M10_Sentiment_Design.md 标注的待实现项）：
  情绪极值 × 宏观政策信号 → 强复合信号（sentiment_resonance）

核心思想：
  单独的政策信号可能被市场半 price-in（预期内），
  单独的情绪极值可能是噪音，
  但两者同时出现时，形成"情绪-基本面共振"，
  历史上往往是趋势加速的起点（2024-09-24 是典型案例）。

触发逻辑：
  RESONANCE_BULLISH = 政策看多信号(intensity≥7) AND 情绪极度恐惧(FG≤25)
    → "价值洼地 + 政策催化" 模式，逆向做多机会
  RESONANCE_BEARISH = 政策看空/无政策 AND 情绪极度贪婪(FG≥80)
    → "过热警告" 模式，追高风险极高
  RESONANCE_POLICY_PANIC = 政策负面冲击 AND 情绪恐惧(FG≤35)
    → "政策+情绪双杀" 模式，规避为主
  RESONANCE_RECOVERY = 情绪从极度恐惧回升 + 北向资金转流入
    → "情绪底部修复" 模式，左侧布局信号

输出：
  生成一个特殊的 MarketSignal（source_type="market_data"，signal_type="sentiment"）
  注入 M2 存储，自动被 M3 判断引擎拾取
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional, Tuple

from core.schemas import MarketSignal

logger = logging.getLogger(__name__)


# ── 共振类型 ─────────────────────────────────────────────────

RESONANCE_NONE = "none"
RESONANCE_BULLISH = "bullish_resonance"       # 政策多 + 情绪极度恐惧（逆向多）
RESONANCE_BEARISH = "bearish_resonance"       # 贪婪过热（预警做空/减仓）
RESONANCE_POLICY_PANIC = "policy_panic"       # 政策负面 + 情绪恐惧（双杀规避）
RESONANCE_RECOVERY = "recovery_signal"        # 情绪底部 + 北向回流（左侧布局）

# 强度阈值
FG_EXTREME_FEAR = 20.0
FG_FEAR = 35.0
FG_GREED = 65.0
FG_EXTREME_GREED = 80.0
POLICY_SIGNAL_MIN_INTENSITY = 7.0       # 政策信号强度下限
NORTHBOUND_RECOVERY_THRESHOLD = 30.0   # 北向资金转正触发恢复信号（亿）


class SentimentResonanceDetector:
    """
    情绪共振检测器

    输入：M10 情绪快照 + 当前批次 MarketSignal 列表
    输出：共振信号（可为 None），注入 M2

    用法：
        detector = SentimentResonanceDetector()
        resonance = detector.detect(snapshot, signals)
        if resonance:
            store.save(resonance)  # 注入 M2
    """

    def detect(
        self,
        snapshot: dict,
        signals: List[MarketSignal],
        batch_id: Optional[str] = None,
    ) -> Optional[MarketSignal]:
        """
        检测情绪共振并生成复合信号

        Args:
            snapshot: M10 最新情绪快照
            signals: 当前批次的 MarketSignal 列表
            batch_id: 注入信号的批次标识

        Returns:
            复合 MarketSignal（如触发），或 None（无共振）
        """
        if not snapshot:
            return None

        fg = float(snapshot.get("fear_greed_index", 50.0))
        nb = float(snapshot.get("northbound_net_billion", 0.0))
        adr = float(snapshot.get("advance_decline_ratio", 0.5))

        # 分析当前批次信号
        policy_signals = self._extract_policy_signals(signals)
        policy_direction, policy_intensity = self._assess_policy_stance(policy_signals)

        # 检测各类共振
        resonance_type, description, intensity, direction = self._classify_resonance(
            fg=fg,
            nb=nb,
            adr=adr,
            policy_direction=policy_direction,
            policy_intensity=policy_intensity,
        )

        if resonance_type == RESONANCE_NONE:
            logger.debug(f"[SentimentResonance] FG={fg:.1f} 无共振")
            return None

        logger.info(
            f"[SentimentResonance] ✨ 触发共振: {resonance_type} | "
            f"FG={fg:.1f} 北向={nb:+.1f}亿 方向={direction} 强度={intensity:.1f}"
        )

        return self._build_resonance_signal(
            resonance_type=resonance_type,
            description=description,
            direction=direction,
            intensity=intensity,
            fg=fg,
            nb=nb,
            adr=adr,
            policy_direction=policy_direction,
            batch_id=batch_id,
        )

    # ── 共振分类逻辑 ─────────────────────────────────────────

    def _classify_resonance(
        self,
        fg: float,
        nb: float,
        adr: float,
        policy_direction: str,
        policy_intensity: float,
    ) -> Tuple[str, str, float, str]:
        """
        返回 (resonance_type, description, intensity, direction)
        """

        # 1. 情绪底部+政策多 → 最强逆向多信号
        if fg <= FG_EXTREME_FEAR and policy_direction == "BULLISH" and policy_intensity >= POLICY_SIGNAL_MIN_INTENSITY:
            intensity = min(10.0, (FG_EXTREME_FEAR - fg) / FG_EXTREME_FEAR * 5 + policy_intensity * 0.5)
            return (
                RESONANCE_BULLISH,
                f"情绪极度恐惧（FG={fg:.0f}）× 强力政策催化（强度{policy_intensity:.1f}）— "
                f"历史验证的逆向多头窗口，典型案例：2024-09-24",
                round(intensity, 1),
                "BULLISH",
            )

        # 2. 情绪恐惧+北向回流 → 情绪底部修复信号
        if fg <= FG_FEAR and nb >= NORTHBOUND_RECOVERY_THRESHOLD and adr >= 0.50:
            intensity = min(8.0, nb / 30.0 * 2 + (FG_FEAR - fg) / FG_FEAR * 3)
            return (
                RESONANCE_RECOVERY,
                f"情绪恐惧（FG={fg:.0f}）转好 + 北向净流入{nb:+.1f}亿 + 涨跌比{adr:.0%}回暖 — "
                f"情绪底部修复信号，可小仓左侧布局",
                round(intensity, 1),
                "BULLISH",
            )

        # 3. 极度贪婪 → 过热预警（无论政策）
        if fg >= FG_EXTREME_GREED:
            intensity = min(9.0, (fg - FG_EXTREME_GREED) / (100 - FG_EXTREME_GREED) * 4 + 5)
            return (
                RESONANCE_BEARISH,
                f"市场极度贪婪（FG={fg:.0f}≥80），追涨风险极高，历史上此区间后续多有回调 — "
                f"建议存量减仓，空仓不追",
                round(intensity, 1),
                "BEARISH",
            )

        # 4. 政策负面+情绪恐惧 → 双杀规避
        if policy_direction == "BEARISH" and policy_intensity >= 6.0 and fg <= FG_FEAR:
            intensity = min(9.0, policy_intensity * 0.6 + (FG_FEAR - fg) / FG_FEAR * 4)
            return (
                RESONANCE_POLICY_PANIC,
                f"政策负面冲击（强度{policy_intensity:.1f}）× 情绪恐惧（FG={fg:.0f}）— "
                f"政策+情绪双杀，规避为主，等待政策转向信号",
                round(intensity, 1),
                "BEARISH",
            )

        return RESONANCE_NONE, "", 0.0, "NEUTRAL"

    # ── 政策信号分析 ─────────────────────────────────────────

    def _extract_policy_signals(self, signals: List[MarketSignal]) -> List[MarketSignal]:
        """筛选政策类信号"""
        policy_types = {"policy_document", "official_announcement"}
        return [
            s for s in signals
            if s.source_type in policy_types or s.signal_type in {"policy", "macro"}
        ]

    def _assess_policy_stance(
        self, policy_signals: List[MarketSignal]
    ) -> Tuple[str, float]:
        """
        评估当前政策信号的整体立场和强度

        Returns:
            (direction, max_intensity)
        """
        if not policy_signals:
            return "NEUTRAL", 0.0

        bullish_intensity = max(
            (s.intensity_score for s in policy_signals if s.signal_direction == "BULLISH"),
            default=0.0,
        )
        bearish_intensity = max(
            (s.intensity_score for s in policy_signals if s.signal_direction == "BEARISH"),
            default=0.0,
        )

        if bullish_intensity > bearish_intensity:
            return "BULLISH", bullish_intensity
        if bearish_intensity > bullish_intensity:
            return "BEARISH", bearish_intensity
        return "NEUTRAL", max(bullish_intensity, bearish_intensity)

    # ── 信号构建 ─────────────────────────────────────────────

    def _build_resonance_signal(
        self,
        resonance_type: str,
        description: str,
        direction: str,
        intensity: float,
        fg: float,
        nb: float,
        adr: float,
        policy_direction: str,
        batch_id: Optional[str],
    ) -> MarketSignal:
        """构建共振复合信号（MarketSignal 格式，可注入 M2）"""
        import uuid

        # 根据共振类型设置时效性
        horizon_map = {
            RESONANCE_BULLISH: "SHORT",
            RESONANCE_RECOVERY: "SHORT",
            RESONANCE_BEARISH: "SHORT",
            RESONANCE_POLICY_PANIC: "SHORT",
        }
        confidence_map = {
            RESONANCE_BULLISH: min(9, int(intensity * 0.9)),
            RESONANCE_RECOVERY: min(8, int(intensity * 0.85)),
            RESONANCE_BEARISH: min(8, int(intensity * 0.8)),
            RESONANCE_POLICY_PANIC: min(9, int(intensity * 0.9)),
        }

        label_map = {
            RESONANCE_BULLISH: f"情绪共振·逆向多头 FG={fg:.0f}",
            RESONANCE_RECOVERY: f"情绪共振·底部修复 北向{nb:+.0f}亿",
            RESONANCE_BEARISH: f"情绪共振·过热预警 FG={fg:.0f}",
            RESONANCE_POLICY_PANIC: f"情绪共振·政策双杀 FG={fg:.0f}",
        }

        return MarketSignal(
            signal_id=f"resonance_{resonance_type}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}",
            signal_type="sentiment",
            signal_label=label_map.get(resonance_type, f"情绪共振·{resonance_type}"),
            description=description,
            evidence_text=(
                f"情绪数据：恐贪指数={fg:.1f}, 北向资金={nb:+.1f}亿, 涨跌比={adr:.1%}\n"
                f"政策立场：{policy_direction}（强度{0:.1f}）\n"
                f"共振类型：{resonance_type}"
            ),
            affected_markets=["A_SHARE"],
            affected_instruments=["510300.SH", "000300.SH"],
            signal_direction=direction,
            event_time=datetime.now(),
            collected_time=datetime.now(),
            time_horizon=horizon_map.get(resonance_type, "SHORT"),
            intensity_score=int(round(intensity)),
            confidence_score=confidence_map.get(resonance_type, int(intensity * 0.8)),
            timeliness_score=9,
            source_type="market_data",
            source_ref="M10.SentimentEngine + M3.SentimentResonance",
            logic_frame={
                "what_changed": (
                    "情绪共振触发: " + resonance_type +
                    f", FG={fg:.0f}, 北向={nb:+.1f}亿, 涨跌比={adr:.0%}"
                ),
                "change_direction": direction,
                "affects": ["A_SHARE"],
            },
            batch_id=batch_id or f"resonance_{datetime.now().strftime('%Y%m%d')}",
        )


# ── 便捷函数 ──────────────────────────────────────────────────

def check_resonance(
    snapshot: dict,
    signals: List[MarketSignal],
    auto_inject: bool = False,
    batch_id: Optional[str] = None,
) -> Optional[MarketSignal]:
    """
    检测情绪共振，可选自动注入 M2

    Args:
        snapshot: M10 最新快照
        signals: 当前批次信号
        auto_inject: True 时自动将共振信号存入 M2
        batch_id: 注入批次标识

    Returns:
        复合信号或 None
    """
    detector = SentimentResonanceDetector()
    resonance = detector.detect(snapshot, signals, batch_id=batch_id)

    if resonance and auto_inject:
        try:
            from m2_storage.signal_store import SignalStore
            store = SignalStore()
            store.save(resonance, batch_id=batch_id)
            logger.info(f"[SentimentResonance] 已注入 M2: {resonance.signal_id}")
        except Exception as e:
            logger.warning(f"[SentimentResonance] 注入 M2 失败: {e}")

    return resonance
