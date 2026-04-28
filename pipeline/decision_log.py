"""
pipeline/decision_log.py — 决策日志模块

记录AI每一次决策的完整链路：异动发现 → 溯源结果 → M3判断 → 趋势判断 → 最终决定
每条记录包含：看到了什么、想了什么、做了什么、为什么做/不做。

数据流：
  M12异动发现  → DecisionLog.record_anomaly()
  M12溯源结果  → DecisionLog.record_causation()
  M3判断结果   → DecisionLog.record_m3_judgment()
  M12趋势判断  → DecisionLog.record_trend()
  M4行动设计   → DecisionLog.record_action()
  开仓/放弃    → DecisionLog.record_outcome()
  每日结算     → DecisionLog.generate_daily_report()

所有记录写JSON文件，不删除，供复盘使用。
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DECISION_DIR = Path("data/decisions")
DAILY_REPORT_DIR = Path("data/daily_reports")


class DecisionRecord:
    """单次决策的完整记录。"""

    def __init__(self, decision_id: str = None):
        self.id = decision_id or f"dec_{uuid.uuid4().hex[:10]}"
        self.timestamp: str = datetime.now().isoformat()
        self.instrument: str = ""
        self.market: str = ""

        # Step 1: 异动发现
        self.anomaly_detected: bool = False
        self.anomaly_type: str = ""
        self.anomaly_price_change_pct: float = 0.0
        self.anomaly_atr_multiple: float = 0.0
        self.anomaly_sigma_multiple: float = 0.0
        self.anomaly_volume_ratio: float = 0.0
        self.anomaly_is_limit_up: bool = False

        # Step 2: 溯源结果
        self.causation_type: str = ""
        self.causation_has_cause: bool = False
        self.causation_signal_count: int = 0
        self.causation_signals: List[Dict] = []
        self.causation_skip_reason: str = ""

        # Step 3: M3判断
        self.m3_judged: bool = False
        self.m3_opportunity: Optional[Dict] = None
        self.m3_skip_reason: str = ""
        self.m3_priority: str = ""
        self.m3_direction: str = ""
        self.m3_score: float = 0.0
        self.m3_fallback: bool = False

        # Step 4: 趋势判断
        self.trend_stage: str = ""
        self.trend_remaining_upside_pct: float = 0.0
        self.trend_catalyst_persistence: str = ""
        self.trend_skip_reason: str = ""

        # Step 5: 行动设计
        self.action_taken: str = ""
        self.action_plan_id: str = ""
        self.stop_loss_pct: float = 0.0
        self.take_profit_pct: float = 0.0
        self.position_id: str = ""
        self.entry_price: float = 0.0

        # 最终结果
        self.outcome: str = ""
        self.reason: str = ""
        self.full_chain: List[str] = []

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "instrument": self.instrument,
            "market": self.market,
            "anomaly_detected": self.anomaly_detected,
            "anomaly_type": self.anomaly_type,
            "anomaly_price_change_pct": self.anomaly_price_change_pct,
            "anomaly_atr_multiple": self.anomaly_atr_multiple,
            "anomaly_sigma_multiple": self.anomaly_sigma_multiple,
            "anomaly_volume_ratio": self.anomaly_volume_ratio,
            "anomaly_is_limit_up": self.anomaly_is_limit_up,
            "causation_type": self.causation_type,
            "causation_has_cause": self.causation_has_cause,
            "causation_signal_count": self.causation_signal_count,
            "causation_signals": self.causation_signals,
            "causation_skip_reason": self.causation_skip_reason,
            "m3_judged": self.m3_judged,
            "m3_opportunity": self.m3_opportunity,
            "m3_skip_reason": self.m3_skip_reason,
            "m3_priority": self.m3_priority,
            "m3_direction": self.m3_direction,
            "m3_score": self.m3_score,
            "m3_fallback": self.m3_fallback,
            "trend_stage": self.trend_stage,
            "trend_remaining_upside_pct": self.trend_remaining_upside_pct,
            "trend_catalyst_persistence": self.trend_catalyst_persistence,
            "trend_skip_reason": self.trend_skip_reason,
            "action_taken": self.action_taken,
            "action_plan_id": self.action_plan_id,
            "stop_loss_pct": self.stop_loss_pct,
            "take_profit_pct": self.take_profit_pct,
            "position_id": self.position_id,
            "entry_price": self.entry_price,
            "outcome": self.outcome,
            "reason": self.reason,
            "full_chain": self.full_chain,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "DecisionRecord":
        r = cls(decision_id=d.get("id"))
        for k, v in d.items():
            if hasattr(r, k):
                setattr(r, k, v)
        return r


class DecisionLog:
    """决策日志管理器。

    每次M12扫描的每个异动，创建一条DecisionRecord，
    沿着决策链路逐步填充，最终持久化到JSON文件。
    所有数据保留，不删除，供复盘使用。
    """

    def __init__(self, date_str: str = None):
        self.today = date_str or date.today().isoformat()
        self.records: Dict[str, DecisionRecord] = {}
        self._load_today()

    def _load_today(self):
        today_file = DECISION_DIR / f"decisions_{self.today}.json"
        if today_file.exists():
            try:
                data = json.loads(today_file.read_text(encoding="utf-8"))
                for d in data:
                    r = DecisionRecord.from_dict(d)
                    self.records[r.id] = r
            except Exception as e:
                logger.warning(f"[DecisionLog] load failed: {e}")

    def _save_today(self):
        DECISION_DIR.mkdir(parents=True, exist_ok=True)
        today_file = DECISION_DIR / f"decisions_{self.today}.json"
        data = [r.to_dict() for r in self.records.values()]
        today_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    # ── Step 1: 异动发现 ─────────────────────────────────────

    def record_anomaly(
        self,
        instrument: str,
        market: str,
        anomaly_type: str,
        price_change_pct: float,
        atr_multiple: float,
        sigma_multiple: float,
        volume_ratio: float,
        is_limit_up: bool = False,
    ) -> DecisionRecord:
        r = DecisionRecord()
        r.instrument = instrument
        r.market = market
        r.anomaly_detected = True
        r.anomaly_type = anomaly_type
        r.anomaly_price_change_pct = price_change_pct
        r.anomaly_atr_multiple = atr_multiple
        r.anomaly_sigma_multiple = sigma_multiple
        r.anomaly_volume_ratio = volume_ratio
        r.anomaly_is_limit_up = is_limit_up
        r.full_chain.append(
            f"1.ANOMALY: {instrument} {price_change_pct:+.1f}% "
            f"type={anomaly_type} sigma={sigma_multiple:.1f} atr={atr_multiple:.1f} vol={volume_ratio:.1f}"
        )
        self.records[r.id] = r
        self._save_today()
        return r

    # ── Step 2: 溯源结果 ─────────────────────────────────────

    def record_causation(
        self,
        record: DecisionRecord,
        causation_type: str,
        has_cause: bool,
        signal_count: int,
        signals: List[Dict] = None,
        skip_reason: str = "",
    ):
        record.causation_type = causation_type
        record.causation_has_cause = has_cause
        record.causation_signal_count = signal_count
        record.causation_signals = (signals or [])[:3]
        record.causation_skip_reason = skip_reason

        if not has_cause:
            record.outcome = "SKIPPED"
            record.reason = skip_reason or "no_cause"
            record.full_chain.append(
                f"2.CAUSATION: no cause found (type={causation_type}), SKIPPED"
            )
        else:
            signal_labels = [
                s.get("signal_label", "?")[:30] for s in (signals or [])[:3]
            ]
            record.full_chain.append(
                f"2.CAUSATION: has_cause type={causation_type} "
                f"signals={signal_count} labels={signal_labels}"
            )
        self._save_today()

    # ── Step 3: M3判断 ───────────────────────────────────────

    def record_m3_judgment(
        self,
        record: DecisionRecord,
        judged: bool,
        opportunity: Dict = None,
        skip_reason: str = "",
        fallback: bool = False,
        priority: str = "",
        direction: str = "",
        score: float = 0.0,
    ):
        record.m3_judged = judged
        record.m3_opportunity = opportunity
        record.m3_skip_reason = skip_reason
        record.m3_fallback = fallback
        record.m3_priority = priority
        record.m3_direction = direction
        record.m3_score = score

        if fallback:
            record.full_chain.append(
                f"3.M3: FALLBACK (LLM unavailable), using M12 hardcoded judgment"
            )
        elif not judged or not opportunity:
            record.outcome = "SKIPPED"
            record.reason = skip_reason or "m3_no_opportunity"
            record.full_chain.append(
                f"3.M3: judged no opportunity, SKIPPED ({skip_reason})"
            )
        else:
            record.full_chain.append(
                f"3.M3: opportunity found priority={priority} "
                f"dir={direction} score={score:.1f}"
            )
        self._save_today()

    # ── Step 4: 趋势判断 ─────────────────────────────────────

    def record_trend(
        self,
        record: DecisionRecord,
        stage: str,
        remaining_upside_pct: float = 0.0,
        catalyst_persistence: str = "",
        skip_reason: str = "",
    ):
        record.trend_stage = stage
        record.trend_remaining_upside_pct = remaining_upside_pct
        record.trend_catalyst_persistence = catalyst_persistence
        record.trend_skip_reason = skip_reason

        if stage == "LATE":
            record.outcome = "SKIPPED"
            record.reason = f"trend_LATE upside={remaining_upside_pct:.1f}%"
            record.full_chain.append(
                f"4.TREND: LATE stage, SKIPPED (upside={remaining_upside_pct:.1f}%)"
            )
        else:
            record.full_chain.append(
                f"4.TREND: {stage} upside={remaining_upside_pct:.1f}% "
                f"persistence={catalyst_persistence}"
            )
        self._save_today()

    # ── Step 5: 行动/结果 ─────────────────────────────────────

    def record_action(
        self,
        record: DecisionRecord,
        action_taken: str,
        reason: str = "",
        plan_id: str = "",
        stop_loss_pct: float = 0.0,
        take_profit_pct: float = 0.0,
        position_id: str = "",
        entry_price: float = 0.0,
    ):
        record.action_taken = action_taken
        record.reason = reason
        record.action_plan_id = plan_id
        record.stop_loss_pct = stop_loss_pct
        record.take_profit_pct = take_profit_pct
        record.position_id = position_id
        record.entry_price = entry_price
        if record.outcome != "SKIPPED":
            record.outcome = action_taken
        record.full_chain.append(
            f"5.ACTION: {action_taken} reason={reason} "
            f"plan={plan_id} SL={stop_loss_pct}% TP={take_profit_pct}%"
        )
        self._save_today()

    # ── 查询 ─────────────────────────────────────────────────

    def get_record(self, decision_id: str) -> Optional[DecisionRecord]:
        return self.records.get(decision_id)

    def get_today_records(self) -> List[DecisionRecord]:
        return list(self.records.values())

    def get_records_by_outcome(self, outcome: str) -> List[DecisionRecord]:
        return [r for r in self.records.values() if r.outcome == outcome]

    def get_records_by_instrument(self, instrument: str) -> List[DecisionRecord]:
        return [r for r in self.records.values() if r.instrument == instrument]

    # ── 每日报告 ─────────────────────────────────────────────

    def generate_daily_report(self) -> Dict:
        """生成每日结构化报告，用于复盘。"""
        records = list(self.records.values())

        total_anomalies = sum(1 for r in records if r.anomaly_detected)
        skipped_no_cause = sum(1 for r in records if r.causation_skip_reason and "no_cause" in r.causation_skip_reason)
        skipped_m3 = sum(1 for r in records if r.m3_skip_reason and not r.m3_fallback)
        skipped_late = sum(1 for r in records if r.trend_skip_reason and "LATE" in r.trend_skip_reason)
        opened = sum(1 for r in records if r.action_taken == "OPENED")
        watch = sum(1 for r in records if r.action_taken == "WATCH_ONLY")
        m3_fallback = sum(1 for r in records if r.m3_fallback)

        by_market = {}
        by_outcome = {}
        by_anomaly_type = {}
        by_trend_stage = {}
        by_causation_type = {}
        decision_chains = []

        for r in records:
            by_market[r.market] = by_market.get(r.market, 0) + 1
            by_outcome[r.outcome] = by_outcome.get(r.outcome, 0) + 1
            by_anomaly_type[r.anomaly_type] = by_anomaly_type.get(r.anomaly_type, 0) + 1
            if r.trend_stage:
                by_trend_stage[r.trend_stage] = by_trend_stage.get(r.trend_stage, 0) + 1
            if r.causation_type:
                by_causation_type[r.causation_type] = by_causation_type.get(r.causation_type, 0) + 1
            if r.full_chain:
                decision_chains.append({
                    "instrument": r.instrument,
                    "chain": r.full_chain,
                    "outcome": r.outcome,
                    "reason": r.reason,
                })

        report = {
            "date": self.today,
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_anomalies": total_anomalies,
                "skipped_no_cause": skipped_no_cause,
                "skipped_m3_no_opportunity": skipped_m3,
                "skipped_trend_late": skipped_late,
                "opened_positions": opened,
                "watch_only": watch,
                "m3_fallback_used": m3_fallback,
            },
            "by_market": by_market,
            "by_outcome": by_outcome,
            "by_anomaly_type": by_anomaly_type,
            "by_trend_stage": by_trend_stage,
            "by_causation_type": by_causation_type,
            "decision_chains": decision_chains,
            "full_records": [r.to_dict() for r in records],
        }

        DAILY_REPORT_DIR.mkdir(parents=True, exist_ok=True)
        report_file = DAILY_REPORT_DIR / f"report_{self.today}.json"
        report_file.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        logger.info(f"[DecisionLog] daily report saved to {report_file}")
        return report

    # ── 历史加载 ─────────────────────────────────────────────

    @staticmethod
    def load_report(date_str: str) -> Optional[Dict]:
        report_file = DAILY_REPORT_DIR / f"report_{date_str}.json"
        if report_file.exists():
            return json.loads(report_file.read_text(encoding="utf-8"))
        return None

    @staticmethod
    def load_decisions(date_str: str) -> List[Dict]:
        dec_file = DECISION_DIR / f"decisions_{date_str}.json"
        if dec_file.exists():
            return json.loads(dec_file.read_text(encoding="utf-8"))
        return []

    @staticmethod
    def list_available_dates() -> List[str]:
        if not DAILY_REPORT_DIR.exists():
            return []
        return sorted(
            f.stem.replace("report_", "")
            for f in DAILY_REPORT_DIR.glob("report_*.json")
        )