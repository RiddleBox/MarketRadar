"""
m6_retrospective/retrospective.py — 复盘归因引擎

对已完结的机会/交易进行结构化归因分析。
结果写入 data/retrospectives/ 目录。
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict

from core.schemas import OpportunityObject, Position, PositionStatus
from core.llm_client import LLMClient

logger = logging.getLogger(__name__)

RETRO_DIR = Path(__file__).parent.parent / "data" / "retrospectives"


class RetrospectiveEngine:
    """复盘归因引擎

    职责：
      1. 对单次机会+持仓进行 LLM 归因分析
      2. 批量扫描已关闭持仓，自动触发复盘
      3. 汇总历史复盘，计算质量分布/模式
      4. 将关键教训写回 M8 知识库
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()
        RETRO_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 核心：单次复盘
    # ------------------------------------------------------------------

    def analyze(
        self,
        opportunity: OpportunityObject,
        position: Optional[Position],
        outcome: str,          # HIT / MISS / STOP_LOSS / TAKE_PROFIT / EXPIRED / MANUAL
        notes: str = "",
        write_to_knowledge: bool = False,
    ) -> dict:
        """执行复盘分析

        Args:
            opportunity: 被复盘的机会对象
            position:    关联持仓（可为 None，表示机会未转化为持仓）
            outcome:     结果类型
            notes:       人工备注
            write_to_knowledge: 是否将教训写入 M8 知识库

        Returns:
            复盘报告 dict（含 retro_id / analysis / scores）
        """
        logger.info(f"[M6] 复盘 opp={opportunity.opportunity_id} outcome={outcome}")

        messages = [
            {"role": "system", "content": RETRO_SYSTEM_PROMPT},
            {"role": "user", "content": self._build_prompt(opportunity, position, outcome, notes)},
        ]

        try:
            raw = self.llm.chat_completion(messages, module_name="m6_retrospective")
            analysis = self._parse_json(raw)
        except Exception as e:
            logger.error(f"[M6] LLM 分析失败: {e}")
            analysis = {
                "signal_quality_score": 0,
                "judgment_quality_score": 0,
                "timing_quality_score": 0,
                "luck_vs_skill": "分析失败",
                "assumption_verification": "分析失败",
                "key_lesson": str(e),
                "system_improvement": "",
                "error": str(e),
            }

        # 计算综合质量分（0-5，三维平均）
        composite_score = round(
            (
                analysis.get("signal_quality_score", 0)
                + analysis.get("judgment_quality_score", 0)
                + analysis.get("timing_quality_score", 0)
            ) / 3,
            2,
        )

        report = {
            "retro_id": f"retro_{uuid.uuid4().hex[:8]}",
            "opportunity_id": opportunity.opportunity_id,
            "opportunity_title": opportunity.opportunity_title,
            "position_id": position.position_id if position else None,
            "instrument": position.instrument if position else None,
            "outcome": outcome,
            "realized_pnl": position.realized_pnl if position else None,
            "composite_score": composite_score,
            "created_at": datetime.now().isoformat(),
            "human_notes": notes,
            "analysis": analysis,
        }

        # 持久化
        out_file = RETRO_DIR / f"{report['retro_id']}.json"
        out_file.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        logger.info(f"[M6] 复盘报告已保存: {out_file.name} | 综合分={composite_score}")

        # 可选：写入 M8 知识库
        if write_to_knowledge and analysis.get("key_lesson"):
            self._write_lesson_to_knowledge(report)

        return report

    # ------------------------------------------------------------------
    # 批量复盘：扫描已关闭持仓
    # ------------------------------------------------------------------

    def batch_analyze_closed_positions(
        self,
        positions: List[Position],
        opportunities_map: Optional[Dict[str, OpportunityObject]] = None,
        write_to_knowledge: bool = False,
    ) -> List[dict]:
        """批量对已关闭持仓进行复盘

        Args:
            positions:        持仓列表（会自动过滤 status=CLOSED）
            opportunities_map: {opportunity_id: OpportunityObject}，用于关联机会
            write_to_knowledge: 是否将教训写入 M8 知识库

        Returns:
            复盘报告列表
        """
        closed = [p for p in positions if p.status == PositionStatus.CLOSED]
        logger.info(f"[M6] 批量复盘: 找到 {len(closed)} 个已关闭持仓")

        # 查找已有复盘，避免重复
        existing_position_ids = self._get_already_retro_position_ids()

        reports = []
        for pos in closed:
            if pos.position_id in existing_position_ids:
                logger.debug(f"[M6] 跳过（已有复盘）: {pos.position_id}")
                continue

            # 构造一个最简机会对象（如果没有传入真实机会）
            opp = None
            if opportunities_map:
                opp = opportunities_map.get(pos.opportunity_id)
            if opp is None:
                opp = self._make_minimal_opportunity(pos)

            # 根据持仓关闭原因推断 outcome
            outcome = self._infer_outcome(pos)

            report = self.analyze(
                opportunity=opp,
                position=pos,
                outcome=outcome,
                write_to_knowledge=write_to_knowledge,
            )
            reports.append(report)

        logger.info(f"[M6] 批量复盘完成: 新增 {len(reports)} 份报告")
        return reports

    # ------------------------------------------------------------------
    # 汇总统计
    # ------------------------------------------------------------------

    def summarize(self) -> dict:
        """加载所有复盘报告，计算汇总统计

        Returns:
            {
              total, win_rate, avg_pnl, avg_composite_score,
              outcome_distribution, score_distribution,
              common_lessons, top_improvements
            }
        """
        reports = self._load_all_reports()
        if not reports:
            return {"total": 0, "message": "暂无复盘记录"}

        total = len(reports)
        outcomes = [r.get("outcome", "") for r in reports]
        pnls = [r.get("realized_pnl") for r in reports if r.get("realized_pnl") is not None]
        scores = [r.get("composite_score", 0) for r in reports]

        wins = sum(1 for p in pnls if p > 0)
        win_rate = wins / len(pnls) if pnls else 0
        avg_pnl = sum(pnls) / len(pnls) if pnls else 0
        avg_score = sum(scores) / len(scores) if scores else 0

        # 结果分布
        outcome_dist: Dict[str, int] = {}
        for o in outcomes:
            outcome_dist[o] = outcome_dist.get(o, 0) + 1

        # 分数分布（0-1/1-2/2-3/3-4/4-5）
        score_dist = {"0-1": 0, "1-2": 0, "2-3": 0, "3-4": 0, "4-5": 0}
        for s in scores:
            if s < 1:
                score_dist["0-1"] += 1
            elif s < 2:
                score_dist["1-2"] += 1
            elif s < 3:
                score_dist["2-3"] += 1
            elif s < 4:
                score_dist["3-4"] += 1
            else:
                score_dist["4-5"] += 1

        # 收集所有教训和改进建议
        lessons = [
            r.get("analysis", {}).get("key_lesson", "")
            for r in reports
            if r.get("analysis", {}).get("key_lesson")
        ]
        improvements = [
            r.get("analysis", {}).get("system_improvement", "")
            for r in reports
            if r.get("analysis", {}).get("system_improvement")
        ]

        return {
            "total": total,
            "win_rate": round(win_rate * 100, 1),
            "avg_pnl_pct": round(avg_pnl * 100, 2),
            "avg_composite_score": round(avg_score, 2),
            "outcome_distribution": outcome_dist,
            "score_distribution": score_dist,
            "recent_lessons": lessons[-5:],
            "recent_improvements": improvements[-5:],
        }

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    def _build_prompt(
        self,
        opp: OpportunityObject,
        pos: Optional[Position],
        outcome: str,
        notes: str,
    ) -> str:
        pnl_str = (
            f"{pos.realized_pnl * 100:.2f}%" if pos and pos.realized_pnl is not None else "N/A"
        )
        duration = ""
        if pos and pos.entry_time and pos.exit_time:
            try:
                delta = pos.exit_time - pos.entry_time
                duration = f"{delta.days}天 {delta.seconds//3600}小时"
            except Exception:
                pass

        assumptions_str = "\n".join([f"  - {a}" for a in opp.key_assumptions]) or "  （无）"
        evidence_str = "\n".join([f"  - {e}" for e in opp.supporting_evidence]) or "  （无）"
        counter_str = "\n".join([f"  - {e}" for e in opp.counter_evidence]) or "  （无）"

        pos_section = ""
        if pos:
            pos_section = f"""
## 持仓信息
品种: {pos.instrument}
方向: {pos.direction.value}
入场价: {pos.entry_price}
出场价: {pos.exit_price or 'N/A'}
持仓时长: {duration or 'N/A'}
止损价: {pos.stop_loss_price or 'N/A'}
止盈价: {pos.take_profit_price or 'N/A'}
关闭原因: {pos.exit_reason or 'N/A'}
"""

        return f"""请对以下机会和交易结果进行结构化复盘分析：

## 机会信息
ID: {opp.opportunity_id}
标题: {opp.opportunity_title}
论点: {opp.opportunity_thesis}
优先级: {opp.priority_level.value}
时机判断（why_now）: {opp.why_now}
风险回报预期: {opp.risk_reward_profile}

## 判断依据
支持证据:
{evidence_str}

反驳证据:
{counter_str}

关键假设:
{assumptions_str}
{pos_section}
## 实际结果
结果类型: {outcome}（HIT=价格到达目标/MISS=机会未成立/STOP_LOSS=触发止损/TAKE_PROFIT=触发止盈/EXPIRED=超时）
实现盈亏: {pnl_str}
人工备注: {notes or '无'}

请按要求输出 JSON 格式复盘报告。"""

    def _parse_json(self, raw: str) -> dict:
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            start = 1
            end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
            text = "\n".join(lines[start:end])
        return json.loads(text)

    def _infer_outcome(self, pos: Position) -> str:
        reason = (pos.exit_reason or "").lower()
        if "止盈" in reason or "take_profit" in reason:
            return "TAKE_PROFIT"
        if "止损" in reason or "stop_loss" in reason:
            return "STOP_LOSS"
        if pos.realized_pnl and pos.realized_pnl > 0:
            return "HIT"
        if pos.realized_pnl and pos.realized_pnl < 0:
            return "MISS"
        return "MANUAL"

    def _make_minimal_opportunity(self, pos: Position) -> OpportunityObject:
        """当没有对应机会对象时，构造一个最简版本用于复盘"""
        from core.schemas import (
            PriorityLevel, Direction, Market, InstrumentType, TimeWindow,
        )
        now = datetime.now()
        return OpportunityObject(
            opportunity_id=pos.opportunity_id,
            opportunity_title=f"{pos.instrument} 交易复盘",
            opportunity_thesis=f"持仓 {pos.instrument}，方向 {pos.direction.value}，入场价 {pos.entry_price}",
            priority_level=PriorityLevel.RESEARCH,
            trade_direction=Direction.BULLISH if pos.direction.value == "BULLISH" else Direction.BEARISH,
            target_markets=[pos.market] if pos.market else [Market.A_SHARE],
            target_instruments=[pos.instrument],
            instrument_types=[pos.instrument_type] if pos.instrument_type else [InstrumentType.STOCK],
            opportunity_window=TimeWindow(
                start=pos.entry_time or now,
                end=(pos.exit_time or now) + timedelta(seconds=1) if (pos.exit_time or now) <= (pos.entry_time or now) else (pos.exit_time or now),
                confidence_level=0.5,
            ),
            why_now="持仓已关闭，进行事后复盘",
            related_signals=[pos.plan_id],
            supporting_evidence=[f"{pos.instrument} 入场价 {pos.entry_price}"],
            counter_evidence=["事后复盘，无预设反驳证据"],
            key_assumptions=[f"方向 {pos.direction.value} 有效"],
            uncertainty_map=["市场不确定性"],
            risk_reward_profile="",
            next_validation_questions=["持仓结果如何？"],
            judgment_version="retrospective",
            created_at=pos.entry_time or now,
            batch_id=pos.plan_id,
        )

    def _get_already_retro_position_ids(self) -> set:
        ids = set()
        for f in RETRO_DIR.glob("retro_*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if data.get("position_id"):
                    ids.add(data["position_id"])
            except Exception:
                pass
        return ids

    def _load_all_reports(self) -> List[dict]:
        reports = []
        for f in sorted(RETRO_DIR.glob("retro_*.json")):
            try:
                reports.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                pass
        return reports

    def _write_lesson_to_knowledge(self, report: dict):
        """将关键教训写入 M8 知识库"""
        try:
            from m8_knowledge.knowledge_base import KnowledgeBase
            kb = KnowledgeBase()
            lesson = report["analysis"].get("key_lesson", "")
            improvement = report["analysis"].get("system_improvement", "")
            if lesson:
                kb.add_entry(
                    category="retrospective_lessons",
                    title=f"复盘教训: {report.get('opportunity_title', '')}",
                    content=f"结果: {report['outcome']} | 盈亏: {report.get('realized_pnl')}\n\n{lesson}\n\n改进建议: {improvement}",
                    tags=["retrospective", report.get("outcome", "").lower()],
                    source_ref=report["retro_id"],
                )
        except Exception as e:
            logger.warning(f"[M6] 写入 M8 失败: {e}")


# ─────────────────────────────────────────────────────────────
# Prompt
# ─────────────────────────────────────────────────────────────

RETRO_SYSTEM_PROMPT = """你是一位专业的量化交易复盘分析师。
任务：对一次机会判断和交易结果进行结构化归因分析。

归因框架（四个维度）：
1. 信号质量：M1 提取的信号是否准确、完整、无遗漏？
2. 机会判断：M3 的论点是否成立？假设是否得到验证？论点逻辑是否严密？
3. 时机判断：why_now 的判断是否正确？入场/出场时机是否恰当？
4. 运气vs判断力：区分"因为正确的理由走对"和"碰巧走对"。

评分标准（每项 1-5 分）：
  5分 = 完全正确，无可挑剔
  4分 = 基本正确，有小瑕疵
  3分 = 一半对一半
  2分 = 主要判断有误，结果靠运气
  1分 = 完全错误

重要：教训要具体可操作，不要泛泛而谈。
"下次要更谨慎" → 无效
"当资金流信号与技术信号背离时，应降低 M3 的置信度权重" → 有效

输出严格 JSON 格式，字段如下：
{
  "signal_quality_score": <1-5整数>,
  "signal_quality_comment": "<50字内>",
  "judgment_quality_score": <1-5整数>,
  "judgment_quality_comment": "<50字内>",
  "timing_quality_score": <1-5整数>,
  "timing_quality_comment": "<50字内>",
  "luck_vs_skill": "<这次结果更多来自运气还是判断力？一句话说明>",
  "assumption_verification": "<关键假设哪些成立，哪些未成立>",
  "key_lesson": "<最重要的一条教训，要具体可操作>",
  "system_improvement": "<一条可操作的系统改进建议，指向具体模块和规则>"
}"""
