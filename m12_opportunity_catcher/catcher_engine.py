"""
m12_opportunity_catcher/catcher_engine.py — 机会补牢主引擎

设计原则（见 PRINCIPLES.md）：
  1. 价格是最终验证
  2. 溯因必须有证据
  3. 止损比入场更重要
  4. 趋势阶段是核心判断
  7. 多策略平行验证
  8. 信号溯源标记 origin="opportunity_catcher"

编排流程：
  异动检测 → 反向溯源 → 趋势判断 → 机会生成

涨停股不入场，标记观察池。
空列表 [] 是合法输出。
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from core.schemas import (
    AnomalyType,
    CausationResult,
    Direction,
    EntryConstraint,
    InstrumentType,
    Market,
    PriceAnomaly,
    PriorityLevel,
    RetroOpportunity,
    SignalType,
    SourceType,
    StopLossConfig,
    MarketSignal,
    OpportunityObject,
    OpportunityScore,
    TrendAssessment,
    TrendStage,
    TimeWindow,
)

from m12_opportunity_catcher.anomaly_detector import AnomalyDetector
from m12_opportunity_catcher.backward_causation import BackwardCausation
from m12_opportunity_catcher.trend_stage import TrendAssessor
from m12_opportunity_catcher.market_strategies import get_strategy, MarketAnomalyStrategy
from pipeline.decision_log import DecisionLog

logger = logging.getLogger(__name__)


class OpportunityCatcherEngine:
    """机会补牢主引擎

    编排流程（按 DESIGN.md）：
    异动检测 → 反向溯源(M0采集+M1解码+M2存储) → M3判断 → 趋势判断 → 机会生成

    默认自动初始化 JudgmentEngine（M3）和 SignalStore（M2），
    确保每条异动都走完整管线。LLM不可用时降级到硬编码判断。

    每个异动的决策过程通过 DecisionLog 完整记录，供复盘使用。
    """

    def __init__(
        self,
        anomaly_detector: AnomalyDetector = None,
        backward_causation: BackwardCausation = None,
        trend_assessor: TrendAssessor = None,
        signal_store=None,
        llm_client=None,
        m3_engine=None,
        decision_log: DecisionLog = None,
        m13_agent=None,
    ):
        self.anomaly_detector = anomaly_detector or AnomalyDetector()
        self.llm_client = llm_client
        self.m13_agent = m13_agent  # M13调研代理

        # M2 SignalStore：存储溯源信号，供M3查询历史
        self.signal_store = signal_store
        if self.signal_store is None:
            try:
                from m2_storage.signal_store import SignalStore
                self.signal_store = SignalStore()
            except Exception as e:
                logger.warning(f"[CatcherEngine] SignalStore init failed: {e}")

        # M3 JudgmentEngine：对溯源信号做完整判断（主路径）
        self.m3_engine = m3_engine
        if self.m3_engine is None:
            try:
                from m3_judgment.judgment_engine import JudgmentEngine
                from core.llm_client import LLMClient
                _llm = llm_client or LLMClient()
                self.m3_engine = JudgmentEngine(
                    llm_client=_llm,
                    signal_store=self.signal_store,
                )
                logger.info("[CatcherEngine] M3 JudgmentEngine initialized (primary path)")
            except Exception as e:
                logger.warning(f"[CatcherEngine] M3 JudgmentEngine init failed: {e}, will use fallback")

        # M12 子模块
        self.backward_causation = backward_causation or BackwardCausation(
            llm_client=self.llm_client,
            signal_store=self.signal_store,
        )
        self.trend_assessor = trend_assessor or TrendAssessor(
            m3_engine=self.m3_engine,
            signal_store=self.signal_store,
        )

        # 决策日志：记录每个异动的完整决策链路
        self.decision_log = decision_log or DecisionLog()

    def run_daily_scan(
        self,
        market: Market,
        price_feed=None,
        stock_list: Optional[List[str]] = None,
        scan_date: Optional[date] = None,
        sentiment_data: Optional[Dict] = None,
    ) -> List[RetroOpportunity]:
        """盘后扫描（A股15:30，港股16:30，美股次日早晨）

        完整流程：异动检测 → 反向溯源 → 趋势判断 → 机会生成
        """
        logger.info(f"[CatcherEngine] run_daily_scan: market={market.value}, date={scan_date}")

        # Step 1: 异动检测
        anomalies = self.anomaly_detector.scan_daily(
            market=market,
            price_feed=price_feed,
            stock_list=stock_list,
            scan_date=scan_date,
        )

        if not anomalies:
            logger.info("[CatcherEngine] no anomalies detected")
            return []

        logger.info(f"[CatcherEngine] detected {len(anomalies)} anomalies")

        # Step 2: 获取历史相关信号
        historical_signals = self._get_historical_signals(market)

        # Step 3: 逐个处理异动
        opportunities = []
        strategy = get_strategy(market)

        for anomaly in anomalies:
            try:
                retro_opp = self._process_anomaly(
                    anomaly, historical_signals, sentiment_data, strategy
                )
                if retro_opp is not None:
                    opportunities.append(retro_opp)
            except Exception as e:
                logger.warning(f"[CatcherEngine] process {anomaly.instrument} failed: {e}")
                continue

        logger.info(f"[CatcherEngine] generated {len(opportunities)} retro opportunities")

        # Generate daily decision report
        try:
            self.decision_log.generate_daily_report()
        except Exception as e:
            logger.warning(f"[CatcherEngine] daily report generation failed: {e}")

        return opportunities

    def run_intraday_scan(
        self,
        market: Market,
        price_feed=None,
        stock_list: Optional[List[str]] = None,
        sentiment_data: Optional[Dict] = None,
    ) -> List[RetroOpportunity]:
        """盘中快速扫描（每30分钟触发一次）

        对涨停股标记观察池，不生成入场机会
        """
        logger.info(f"[CatcherEngine] run_intraday_scan: market={market.value}")

        anomalies = self.anomaly_detector.scan_intraday(
            market=market,
            price_feed=price_feed,
            stock_list=stock_list,
        )

        if not anomalies:
            return []

        strategy = get_strategy(market)

        # 盘中只处理非涨停的异动
        tradable_anomalies = [a for a in anomalies if not a.is_limit_up and not a.is_limit_down]
        limit_up_anomalies = [a for a in anomalies if a.is_limit_up]

        if limit_up_anomalies:
            logger.info(
                f"[CatcherEngine] {len(limit_up_anomalies)} stocks at limit up, moved to watch pool"
            )

        historical_signals = self._get_historical_signals(market)

        opportunities = []
        for anomaly in tradable_anomalies:
            try:
                retro_opp = self._process_anomaly(
                    anomaly, historical_signals, sentiment_data, strategy
                )
                if retro_opp is not None:
                    opportunities.append(retro_opp)
            except Exception as e:
                logger.warning(f"[CatcherEngine] intraday process {anomaly.instrument} failed: {e}")
                continue

        return opportunities

    def _process_anomaly(
        self,
        anomaly: PriceAnomaly,
        historical_signals: List[MarketSignal],
        sentiment_data: Optional[Dict],
        strategy: MarketAnomalyStrategy,
    ) -> Optional[RetroOpportunity]:
        """处理单个异动事件：溯源 → M3判断 → 趋势判断 → 生成机会

        每步决策通过 DecisionLog 完整记录：看到了什么、想了什么、做了什么、为什么。
        """
        # Step 0: 记录异动发现
        rec = self.decision_log.record_anomaly(
            instrument=anomaly.instrument,
            market=anomaly.market.value,
            anomaly_type=anomaly.anomaly_type.value if hasattr(anomaly.anomaly_type, 'value') else str(anomaly.anomaly_type),
            price_change_pct=anomaly.price_change_pct,
            atr_multiple=anomaly.atr_multiple,
            sigma_multiple=anomaly.sigma_multiple,
            volume_ratio=anomaly.volume_ratio,
            is_limit_up=anomaly.is_limit_up,
        )

        # Step 1: 反向溯源（M0→M1→M2），只找原因，不做判断
        causation = self.backward_causation.trace(
            anomaly=anomaly,
            historical_signals=historical_signals,
            sentiment_data=sentiment_data,
        )

        # 记录溯源结果
        signal_summaries = [
            {"signal_id": s.signal_id, "label": s.signal_label[:60], "type": s.signal_type.value}
            for s in causation.causes[:5]
        ]
        self.decision_log.record_causation(
            record=rec,
            causation_type=causation.causation_type,
            has_cause=causation.confidence > 0.0 and causation.causation_type != "unexplained",
            signal_count=len(causation.causes),
            signals=signal_summaries,
            skip_reason="" if causation.confidence > 0.0 else "no_cause",
        )

        # 无因 = 放弃（溯因必须有证据，无因追高=赌博）
        if causation.confidence == 0.0 or causation.causation_type == "unexplained":
            logger.info(
                f"[CatcherEngine] {anomaly.instrument} no cause found "
                f"(type={causation.causation_type}), skipping"
            )
            return None

        # Step 2: M3 judge — 信号送入M3做完整判断
        m3_opp = None
        m3_fallback = False
        if self.m3_engine is not None and causation.causes:
            try:
                m3_results = self.m3_engine.judge(
                    signals=causation.causes[:5],
                    historical_signals=historical_signals,
                    batch_id=f"m12_{anomaly.instrument}_{anomaly.anomaly_date.isoformat()}",
                )
                if m3_results:
                    m3_opp = m3_results[0]
                    logger.info(
                        f"[CatcherEngine] M3 judged {anomaly.instrument}: "
                        f"priority={m3_opp.priority_level}, "
                        f"dir={m3_opp.trade_direction}, "
                        f"score={m3_opp.opportunity_score.overall_score if m3_opp.opportunity_score else 'N/A'}"
                    )
                else:
                    logger.info(
                        f"[CatcherEngine] M3 judged {anomaly.instrument}: no opportunity, skipping"
                    )
            except Exception as e:
                logger.warning(f"[CatcherEngine] M3 judge failed for {anomaly.instrument}: {e}")
                m3_fallback = True

        # 记录M3判断结果
        m3_skip_reason = ""
        m3_priority = ""
        m3_direction = ""
        m3_score = 0.0
        m3_opp_dict = None

        if m3_opp is not None:
            m3_priority = m3_opp.priority_level.value if hasattr(m3_opp.priority_level, 'value') else str(m3_opp.priority_level)
            m3_direction = m3_opp.trade_direction.value if hasattr(m3_opp.trade_direction, 'value') else str(m3_opp.trade_direction)
            m3_score = m3_opp.opportunity_score.overall_score if m3_opp.opportunity_score else 0.0
            try:
                m3_opp_dict = m3_opp.model_dump()
            except Exception:
                m3_opp_dict = {"id": m3_opp.opportunity_id, "title": m3_opp.opportunity_title}
        elif not m3_fallback:
            m3_skip_reason = "m3_no_opportunity"

        self.decision_log.record_m3_judgment(
            record=rec,
            judged=m3_opp is not None or m3_fallback,
            opportunity=m3_opp_dict,
            skip_reason=m3_skip_reason,
            fallback=m3_fallback,
            priority=m3_priority,
            direction=m3_direction,
            score=m3_score,
        )

        # M3认为不构成机会 → 放弃（M3可用时）
        if m3_opp is None and not m3_fallback and self.m3_engine is not None:
            return None

        # Step 3: M12趋势阶段判断（基于价格数据 + M3结果）
        trend = self.trend_assessor.assess(
            anomaly=anomaly,
            causation=causation,
            m3_opportunity=m3_opp,
        )

        # 记录趋势判断
        trend_persistence = ""
        if hasattr(trend, 'catalyst_persistence') and trend.catalyst_persistence:
            trend_persistence = trend.catalyst_persistence.value if hasattr(trend.catalyst_persistence, 'value') else str(trend.catalyst_persistence)

        self.decision_log.record_trend(
            record=rec,
            stage=trend.stage.value,
            remaining_upside_pct=trend.remaining_upside_pct,
            catalyst_persistence=trend_persistence,
            skip_reason="trend_LATE" if trend.stage == TrendStage.LATE else "",
        )

        # LATE阶段放弃
        if trend.stage == TrendStage.LATE:
            logger.info(
                f"[CatcherEngine] {anomaly.instrument} trend stage=LATE, skipping"
            )
            return None

        # Step 4: 生成OpportunityObject
        # 优先使用M3的OpportunityObject（包含M3的完整判断）
        # M3不可用时降级到M12自建（弱判断）
        if m3_opp is not None:
            # 用M3的判断结果，但补充M12特有的止损候选和入场约束
            opportunity = m3_opp
            # 补充M12特有字段
            if opportunity.origin != "opportunity_catcher":
                opportunity.origin = "opportunity_catcher"
            if not opportunity.entry_constraint and anomaly.is_limit_up:
                opportunity.entry_constraint = EntryConstraint(
                    reason="limit_up",
                    expected_entry_time=datetime.combine(
                        anomaly.anomaly_date + timedelta(days=1)
                        if hasattr(anomaly.anomaly_date, 'day') else date.today(),
                        datetime.min.time()
                    ),
                    monitoring_fields={"limit_type": "limit_up", "market": anomaly.market.value},
                )
            logger.info(
                f"[CatcherEngine] {anomaly.instrument}: using M3 judgment, "
                f"priority={opportunity.priority_level.value}, "
                f"dir={opportunity.trade_direction.value}"
            )
        else:
            # M3不可用，降级到M12自建（弱判断，明确标注）
            opportunity = self._build_opportunity(anomaly, causation, trend, strategy)
            if opportunity is None:
                return None
            logger.info(
                f"[CatcherEngine] {anomaly.instrument}: M3 unavailable, "
                f"using M12 fallback judgment"
            )

        # Step 4: 获取止损策略候选
        stop_loss_candidates = strategy.stop_loss_candidates

        # Step 5: 构建RetroOpportunity
        retro = RetroOpportunity(
            opportunity=opportunity,
            anomaly=anomaly,
            causation=causation,
            trend=trend,
            origin="opportunity_catcher",
            stop_loss_candidates=stop_loss_candidates,
            anomaly_type=anomaly.anomaly_type,
            market=anomaly.market,
            trend_stage=trend.stage,
            causation_type=causation.causation_type,
            causation_confidence=causation.confidence,
            volume_ratio=anomaly.volume_ratio,
            atr_multiple=anomaly.atr_multiple,
            sigma_multiple=anomaly.sigma_multiple,
        )

        logger.info(
            f"[CatcherEngine] {anomaly.instrument}: stage={trend.stage.value}, "
            f"confidence={causation.confidence:.0%}, upside={trend.remaining_upside_pct:.1f}%"
        )

        # 记录最终结果
        sl_pct = stop_loss_candidates[0].stop_loss_value if stop_loss_candidates else 0.0
        tp_pct = retro.opportunity.risk_reward_profile if hasattr(retro.opportunity, 'risk_reward_profile') else ""
        self.decision_log.record_action(
            record=rec,
            action_taken="PASSED",
            reason=f"trend={trend.stage.value} upside={trend.remaining_upside_pct:.1f}%",
            plan_id=opportunity.opportunity_id,
            stop_loss_pct=sl_pct,
            take_profit_pct=0.0,
        )

        return retro

    def _build_opportunity(
        self,
        anomaly: PriceAnomaly,
        causation: CausationResult,
        trend: TrendAssessment,
        strategy: MarketAnomalyStrategy,
    ) -> Optional[object]:
        """M12降级自建OpportunityObject（仅当M3不可用时使用）。

        注意：这是弱判断，优先级和评分由硬编码规则决定，
        不如M3的LLM判断准确。M3可用时应优先使用M3的结果。
        """

        # M13调研验证（如果溯源置信度不够高）
        if self.m13_agent and causation.confidence < 0.7:
            try:
                research = self.m13_agent.standard_research(
                    symbol=anomaly.instrument,
                    context=f"价格异动{anomaly.price_change_pct:+.1f}% ({anomaly.anomaly_type.value})"
                )

                # 调整溯源置信度
                causation.confidence += research.confidence_delta

                # 如果发现重大利空，降低置信度
                if research.has_major_negative:
                    causation.confidence *= 0.5
                    logger.warning(
                        f"[M12+M13] 发现重大利空: {anomaly.instrument} - {research.summary}"
                    )

                logger.info(
                    f"[M12+M13] 调研完成: {anomaly.instrument} "
                    f"- 置信度调整: {causation.confidence:.2f}"
                )

            except Exception as e:
                # M13失败不影响主流程
                logger.warning(f"[M12+M13] 调研失败: {e}")

        # 优先级取决于趋势阶段
        if trend.stage == TrendStage.EARLY:
            priority = PriorityLevel.POSITION
            score_overall = 7.0
        elif trend.stage == TrendStage.MIDDLE:
            priority = PriorityLevel.RESEARCH
            score_overall = 5.0
        else:
            return None

        # 入场约束（涨停等）
        entry_constraint = None
        if anomaly.is_limit_up:
            entry_constraint = EntryConstraint(
                reason="limit_up",
                expected_entry_time=datetime.combine(
                    anomaly.anomaly_date + timedelta(days=1)
                    if hasattr(anomaly.anomaly_date, 'day') else date.today(),
                    datetime.min.time()
                ),
                monitoring_fields={"limit_type": "limit_up", "market": anomaly.market.value},
            )

        # 标题
        direction = "看多" if anomaly.price_change_pct > 0 else "看空"
        causation_desc = causation.causation_type if causation.causation_type != "unexplained" else "原因未明"
        title = f"[补牢] {anomaly.instrument} {direction} | {causation_desc} | {trend.stage.value}阶段"

        # 论据
        signals_detail = "; ".join([f"{c.signal_type.value}:{c.signal_label[:20]}" for c in causation.causes[:3]])

        opportunity = OpportunityObject(
            opportunity_id=f"retro_{anomaly.instrument}_{anomaly.anomaly_date.isoformat()}",
            opportunity_title=title,
            opportunity_thesis=f"异动补牢：{anomaly.instrument} {anomaly.price_change_pct:+.1f}% ({anomaly.anomaly_type})，"
                               f"原因:{causation_desc}，趋势:{trend.stage.value}，"
                               f"剩余空间{trend.remaining_upside_pct:.1f}%，"
                               f"置信度{causation.confidence:.0%}",
            target_markets=[anomaly.market],
            target_instruments=[anomaly.instrument],
            trade_direction=Direction.BULLISH if anomaly.price_change_pct > 0 else Direction.BEARISH,
            instrument_types=[InstrumentType.STOCK],
            opportunity_window=TimeWindow(
                start=datetime.combine(anomaly.anomaly_date, datetime.min.time()),
                end=datetime.combine(anomaly.anomaly_date + timedelta(days=7), datetime.min.time()),
                confidence_level=0.7 if trend.stage == TrendStage.EARLY else 0.5,
            ),
            why_now=f"价格异动验证（{anomaly.sigma_multiple:.1f}σ，{anomaly.atr_multiple:.1f}×ATR，量比{anomaly.volume_ratio:.1f}），"
                    f"溯源找到{len(causation.causes)}条相关信号",
            related_signals=[s.signal_id for s in causation.causes[:5]],
            supporting_evidence=[f"ATR倍数: {anomaly.atr_multiple:.2f}"] + [f"σ倍数: {anomaly.sigma_multiple:.2f}"],
            counter_evidence=[f"无法解释比例: {causation.unexplained_ratio:.0%}"] if causation.unexplained_ratio > 0.2 else [],
            key_assumptions=[f"原因({causation.causation_type})持续性: {trend.catalyst_persistence.value}"],
            uncertainty_map=[f"原因不确定性: {causation.unexplained_ratio:.0%}"],
            priority_level=priority,
            opportunity_score=OpportunityScore(
                overall_score=score_overall,
                confidence_score=causation.confidence,
                catalyst_strength=7 if trend.stage == TrendStage.EARLY else 5,
                timeliness=9 if trend.stage == TrendStage.EARLY else 6,
                market_confirmation=int(anomaly.volume_ratio),
                tradability=8 if not anomaly.is_limit_up else 3,
                risk_clarity=7 if causation.confidence >= 0.5 else 4,
                consensus_gap=5,
                signal_consistency=min(len(causation.causes) + 3, 10),
                execution_readiness=0.8 if not anomaly.is_limit_up else 0.2,
            ),
            risk_reward_profile=f"止损{strategy.stop_loss_candidates[0].stop_loss_value if strategy.stop_loss_candidates else 5}%/"
                               f"目标{trend.remaining_upside_pct:.1f}%"
                               f" ({trend.stage.value}阶段补牢)",
            invalidation_conditions=[
                f"原因反转（{causation.causation_type}证伪）",
                f"价格跌破基线价{anomaly.baseline_price:.2f}",
            ],
            next_validation_questions=[
                f"{anomaly.instrument}趋势能否延续？",
                f"原因({causation.causation_type})是否有新证据？",
            ],
            must_watch_indicators=[anomaly.instrument, f"恐贪指数"],
            origin="opportunity_catcher",
            entry_constraint=entry_constraint,
            batch_id=f"retro_{anomaly.anomaly_date.isoformat()}",
        )

        return opportunity

    def _get_historical_signals(self, market: Market) -> List[MarketSignal]:
        """从M2获取近期相关信号"""
        if self.signal_store is None:
            return []

        try:
            from datetime import timedelta
            signals = self.signal_store.query(
                markets=[market],
                limit=50,
                lookback_days=5,
            )
            return signals
        except Exception as e:
            logger.warning(f"[CatcherEngine] signal store query failed: {e}")
            return []