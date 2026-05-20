"""
m1_decoder/local/scorer.py — 规则化评分引擎

用关键词匹配、来源映射和时间差计算替代 LLM 打分。
输入：Extractor 输出的简化信号 dict（不含 scores/description/event_time）
输出：补全所有 MarketSignal 必填字段的完整 dict
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import List

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# intensity_score — 事件类型基准分 + 关键词修正
# ═══════════════════════════════════════════════════════════════

_INTENSITY_KEYWORDS: dict[str, int] = {
    # 宏观/政策类
    "降准": 7, "降息": 8, "加息": 9, "QE": 9, "量化宽松": 9,
    "熔断": 10, "战争": 10, "制裁": 8, "财政刺激": 7, "特别国债": 7,
    "GDP超预期": 6, "CPI暴涨": 7, "PMI跌破50": 6, "通胀": 6,
    # 行业类
    "行业补贴": 6, "禁售": 8, "出口限制": 8, "医保纳入": 7, "集采": 7,
    "牌照": 6, "专项整治": 7,
    # 公司事件
    "停牌": 6, "ST": 8, "退市": 10, "破产": 10, "并购": 7, "回购": 6,
    "大额减持": 7, "增持": 5, "分红": 4, "定增": 6,
    # 资金流
    "净流入": 6, "净流出": 6, "大幅流入": 8, "大幅流出": 8,
    # 英文
    "rate cut": 8, "rate hike": 9, "bankruptcy": 10, "default": 10,
    "sanction": 8, "stimulus": 7, "buyback": 6, "delisting": 10, "downgrade": 5,
}

# 程度修饰词修正
_INTENSITY_MODIFIERS: dict[str, int] = {
    "历史": 2, "创纪录": 2, "首次": 2, "突破": 1, "危机": 3,
    "大幅": 1, "超预期": 1, "重大": 1, "系统性": 2,
    "小幅": -1, "微调": -2, "略有": -2, "温和": -1,
}

# source_type → confidence_score 映射
_CONFIDENCE_BY_SOURCE: dict[str, int] = {
    "official_announcement": 10,
    "policy_document": 10,
    "market_data": 9,
    "news": 7,
    "research_report": 6,
    "market_monitor": 6,
    "manual_input": 5,
    "social_media": 3,
}

# 来源域名修正
_SOURCE_DOMAIN_BONUS: dict[str, int] = {
    "央行": 1, "证监会": 1, "财政部": 1, "发改委": 1,
    "reuters": 1, "bloomberg": 1,
}


class RuleBasedScorer:
    """规则化评分引擎。用确定性规则填充 LLM 不生成的字段。"""

    def process(
        self,
        raw_signals: List[dict],
        source_type: str,
        batch_id: str,
        source_ref: str,
        collected_time: str = None,
    ) -> List[dict]:
        """主入口：补全所有缺失字段，返回完整信号 dict 列表。"""
        if collected_time is None:
            collected_time = datetime.now().isoformat()

        enriched = []
        for sig in raw_signals:
            try:
                sig = self._normalize_signal(sig)
                sig["batch_id"] = batch_id
                sig["source_ref"] = source_ref
                sig["source_type"] = source_type
                sig["collected_time"] = collected_time
                sig["event_time"] = collected_time
                sig["affected_instruments"] = sig.get("affected_instruments", [])
                sig["description"] = self._build_description(sig)
                sig["intensity_score"] = self._score_intensity(sig)
                sig["confidence_score"] = self._score_confidence(source_type, source_ref)
                sig["timeliness_score"] = self._score_timeliness(collected_time)
                enriched.append(sig)
            except Exception as e:
                logger.warning(f"Scorer failed for signal: {e}")
        return enriched

    _VALID_SIGNAL_TYPES = {
        "macro", "industry", "capital_flow", "technical",
        "event_driven", "policy", "sentiment", "anomalous_activity",
    }
    _VALID_DIRECTIONS = {"BULLISH", "BEARISH", "NEUTRAL", "UNCERTAIN"}
    _VALID_HORIZONS = {"SHORT", "MEDIUM", "LONG"}
    _VALID_MARKETS = {"A_SHARE", "HK", "US", "A_FUTURES", "HK_FUTURES", "US_FUTURES"}

    @classmethod
    def _pick_first_valid(cls, value, valid_set, default):
        if isinstance(value, str) and value in valid_set:
            return value
        if isinstance(value, str):
            for part in value.replace("，", ",").replace("/", ",").replace("|", ",").split(","):
                part = part.strip().upper()
                if part in valid_set:
                    return part
        return default

    def _normalize_signal(self, sig: dict) -> dict:
        sig["signal_type"] = self._pick_first_valid(
            sig.get("signal_type", ""), self._VALID_SIGNAL_TYPES, "event_driven"
        )
        sig["signal_direction"] = self._pick_first_valid(
            sig.get("signal_direction", ""), self._VALID_DIRECTIONS, "UNCERTAIN"
        )
        sig["time_horizon"] = self._pick_first_valid(
            sig.get("time_horizon", ""), self._VALID_HORIZONS, "MEDIUM"
        )
        markets = sig.get("affected_markets", ["A_SHARE"])
        if isinstance(markets, str):
            markets = [m.strip().upper() for m in markets.replace("/", ",").split(",")]
        sig["affected_markets"] = [m for m in markets if m in self._VALID_MARKETS] or ["A_SHARE"]
        if "logic_frame" not in sig or not isinstance(sig.get("logic_frame"), dict):
            sig["logic_frame"] = {
                "what_changed": sig.get("signal_label", sig.get("description", "unknown event")),
                "change_direction": sig.get("signal_direction", "UNCERTAIN"),
                "affects": sig.get("affected_instruments", []),
            }
        return sig

    def _build_description(self, sig: dict) -> str:
        label = sig.get("signal_label", "")
        lf = sig.get("logic_frame", {})
        what = lf.get("what_changed", "") if isinstance(lf, dict) else ""
        affects = lf.get("affects", []) if isinstance(lf, dict) else []
        parts = [label]
        if what:
            parts.append(what)
        if affects:
            parts.append(f"影响: {'、'.join(affects)}")
        return "。".join(parts)

    def _score_intensity(self, sig: dict) -> int:
        label = sig.get("signal_label", "")
        evidence = sig.get("evidence_text", "")
        combined = f"{label} {evidence}"

        base_score = 5  # 默认中等

        # 关键词匹配
        for kw, score in _INTENSITY_KEYWORDS.items():
            if kw.lower() in combined.lower():
                base_score = max(base_score, score)

        # 程度修饰词修正
        modifier = 0
        for kw, delta in _INTENSITY_MODIFIERS.items():
            if kw in combined:
                modifier += delta

        # 百分比幅度修正
        pct_match = re.search(r"(\d+(?:\.\d+)?)\s*%", combined)
        if pct_match:
            pct = float(pct_match.group(1))
            if pct > 5:
                modifier += 2
            elif pct >= 3:
                modifier += 1

        score = base_score + modifier
        return max(1, min(10, score))

    def _score_confidence(self, source_type: str, source_ref: str = "") -> int:
        score = _CONFIDENCE_BY_SOURCE.get(source_type, 5)

        # 来源域名修正
        ref_lower = source_ref.lower()
        for domain, bonus in _SOURCE_DOMAIN_BONUS.items():
            if domain in ref_lower:
                score += bonus
                break

        return max(1, min(10, score))

    def _score_timeliness(self, collected_time_str: str) -> int:
        try:
            collected = datetime.fromisoformat(collected_time_str)
            delta_hours = (datetime.now() - collected.replace(tzinfo=None)).total_seconds() / 3600
        except (ValueError, TypeError):
            return 7

        if delta_hours < 1:
            return 10
        elif delta_hours < 4:
            return 9
        elif delta_hours < 12:
            return 8
        elif delta_hours < 24:
            return 7
        elif delta_hours < 72:
            return 5
        elif delta_hours < 168:
            return 3
        else:
            return 1
