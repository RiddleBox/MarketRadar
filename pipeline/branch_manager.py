"""
pipeline/branch_manager.py — 多分支A/B测试管理器

职责：
  1. 管理16个并行测试分支（2×4×2结构）
  2. 对每个机会运行所有相关分支的调整逻辑
  3. 避免重复开仓（同一标的只开一次，但记录所有认可的分支）
  4. 追踪每个分支的胜率、盈亏、持仓时长等指标
  5. 生成分支对比报告

分支结构：
  第一层（信号来源）：
    - A: M12异动检测
    - B: M0信号管道

  第二层（情绪+历史）：
    - 1: 无情绪，无历史
    - 2: 有情绪，无历史
    - 3: 无情绪，有历史
    - 4: 有情绪，有历史

  第三层（M11验证）：
    - a: 无M11
    - b: 有M11

  总计：2 × 4 × 2 = 16个分支
  示例：A1a, A2b, B3a, B4b
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from core.schemas import Direction, OpportunityObject

logger = logging.getLogger(__name__)


@dataclass
class BranchConfig:
    """单个分支的配置和统计指标"""
    branch_id: str  # "A1a", "A2b", etc.
    source: str  # "m12_anomaly" or "signal_pipeline"
    use_sentiment: bool
    use_knowledge_base: bool
    use_m11_validation: bool

    # 追踪指标
    total_opportunities: int = 0  # 看到的机会总数
    positions_opened: int = 0  # 实际开仓数（可能被其他分支共享）
    positions_closed: int = 0  # 平仓数
    win_count: int = 0  # 盈利次数
    total_pnl: float = 0.0  # 累计盈亏（百分比）
    avg_hold_hours: float = 0.0  # 平均持仓时长（小时）

    # 过滤统计
    filtered_by_sentiment: int = 0
    filtered_by_kb: int = 0
    filtered_by_m11: int = 0
    downgraded_by_m11: int = 0


class BranchManager:
    """多分支A/B测试管理器"""

    def __init__(self, trader=None, report_dir: str = "data/branch_reports"):
        """
        Args:
            trader: PaperTrader实例（共享）
            report_dir: 分支报告保存目录
        """
        self.branches = self._init_branches()
        self.trader = trader
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"[BranchManager] 初始化完成，共 {len(self.branches)} 个分支")

    def _init_branches(self) -> Dict[str, BranchConfig]:
        """初始化16个分支配置"""
        branches = {}

        # 第一层：信号来源
        sources = [
            ("A", "m12_anomaly"),
            ("B", "signal_pipeline"),
        ]

        # 第二层：情绪+历史
        sentiment_kb_combos = [
            ("1", False, False),  # 无情绪，无历史
            ("2", True, False),   # 有情绪，无历史
            ("3", False, True),   # 无情绪，有历史
            ("4", True, True),    # 有情绪，有历史
        ]

        # 第三层：M11
        m11_options = [
            ("a", False),  # 无M11
            ("b", True),   # 有M11
        ]

        for src_prefix, src_type in sources:
            for combo_suffix, use_sent, use_kb in sentiment_kb_combos:
                for m11_suffix, use_m11 in m11_options:
                    branch_id = f"{src_prefix}{combo_suffix}{m11_suffix}"
                    branches[branch_id] = BranchConfig(
                        branch_id=branch_id,
                        source=src_type,
                        use_sentiment=use_sent,
                        use_knowledge_base=use_kb,
                        use_m11_validation=use_m11,
                    )

        return branches

    def process_opportunity(
        self,
        opportunity: OpportunityObject,
        source: str,  # "m12_anomaly" or "signal_pipeline"
        feed_cls,
    ) -> List[str]:
        """
        对单个机会运行所有相关分支的调整逻辑。

        Args:
            opportunity: 原始机会对象
            source: 机会来源
            feed_cls: 价格数据源类

        Returns:
            开仓的position_id列表（可能为空）
        """
        # 找到匹配source的所有分支（8个）
        relevant_branches = [
            b for b in self.branches.values()
            if b.source == source
        ]

        # 收集所有认可这个机会的分支
        approving_branches = []

        for branch in relevant_branches:
            branch.total_opportunities += 1

            # 克隆机会对象（避免互相影响）
            opp_copy = self._clone_opportunity(opportunity)

            # 根据分支配置调整机会
            adjusted_opp = self._adjust_opportunity(
                opp_copy,
                branch
            )

            if adjusted_opp is None:
                # 被过滤掉
                continue

            approving_branches.append({
                "branch_id": branch.branch_id,
                "branch": branch,
                "adjusted_opp": adjusted_opp,
                "adjusted_intensity": adjusted_opp.score.intensity,
            })

        if not approving_branches:
            logger.debug(f"[BranchManager] {opportunity.instrument} 被所有分支拒绝")
            return []

        # 只开一次仓，使用最高强度的分支配置
        best_branch_info = max(approving_branches, key=lambda x: x["adjusted_intensity"])

        position_ids = self._open_position_for_branches(
            best_branch_info["adjusted_opp"],
            approving_branches,
            feed_cls
        )

        return position_ids

    def _clone_opportunity(self, opp: OpportunityObject) -> OpportunityObject:
        """深拷贝机会对象"""
        return opp.model_copy(deep=True)

    def _adjust_opportunity(
        self,
        opp: OpportunityObject,
        branch: BranchConfig,
    ) -> Optional[OpportunityObject]:
        """
        根据分支配置调整机会强度。

        Returns:
            调整后的机会对象，或None（被过滤）
        """
        original_intensity = opp.score.intensity
        adjustment_reasons = []

        # M10情绪调整
        if branch.use_sentiment:
            sentiment_adj = self._apply_sentiment_adjustment(opp)
            if sentiment_adj is None:
                branch.filtered_by_sentiment += 1
                return None
            opp = sentiment_adj["opportunity"]
            if sentiment_adj["reasons"]:
                adjustment_reasons.extend(sentiment_adj["reasons"])

        # M8历史教训调整
        if branch.use_knowledge_base:
            kb_adj = self._apply_kb_adjustment(opp)
            if kb_adj is None:
                branch.filtered_by_kb += 1
                return None
            opp = kb_adj["opportunity"]
            if kb_adj["reasons"]:
                adjustment_reasons.extend(kb_adj["reasons"])

        # M11 Agent验证
        if branch.use_m11_validation:
            m11_adj = self._apply_m11_validation(opp)
            if m11_adj is None:
                branch.filtered_by_m11 += 1
                return None
            opp = m11_adj["opportunity"]
            if m11_adj.get("downgraded"):
                branch.downgraded_by_m11 += 1
            if m11_adj["reasons"]:
                adjustment_reasons.extend(m11_adj["reasons"])

        # 记录调整信息
        if adjustment_reasons:
            opp.metadata = opp.metadata or {}
            opp.metadata[f"branch_{branch.branch_id}_adjustment"] = {
                "original_intensity": original_intensity,
                "adjusted_intensity": opp.score.intensity,
                "reasons": adjustment_reasons
            }

        return opp

    def _apply_sentiment_adjustment(self, opp: OpportunityObject) -> Optional[dict]:
        """应用M10情绪调整"""
        try:
            from m10_sentiment.sentiment_store import SentimentStore
            store = SentimentStore()
            sentiment = store.get_latest_snapshot()

            if not sentiment:
                return {"opportunity": opp, "reasons": []}

            fg = sentiment.get("fear_greed_index", 50.0)
            direction = opp.direction
            adjustment = 0.0
            reasons = []

            # 极度恐慌时，逆向做多机会加分
            if fg < 20 and direction == Direction.LONG:
                adjustment += 0.15
                reasons.append(f"极度恐慌(FG={fg:.0f})，逆向做多+15%")

            # 极度贪婪时，做多机会减分
            elif fg > 80 and direction == Direction.LONG:
                adjustment -= 0.15
                reasons.append(f"极度贪婪(FG={fg:.0f})，做多-15%")

            # 北向资金方向一致性
            nb_direction = sentiment.get("northbound_direction")
            if nb_direction and nb_direction == direction.value:
                adjustment += 0.05
                reasons.append("北向资金方向一致+5%")

            # 应用调整
            new_intensity = max(0.0, min(1.0, opp.score.intensity + adjustment))
            opp.score.intensity = new_intensity

            return {"opportunity": opp, "reasons": reasons}

        except Exception as e:
            logger.warning(f"[BranchManager] M10情绪调整失败: {e}")
            return {"opportunity": opp, "reasons": []}

    def _apply_kb_adjustment(self, opp: OpportunityObject) -> Optional[dict]:
        """应用M8历史教训调整"""
        try:
            from m8_knowledge.knowledge_base import KnowledgeBase
            kb = KnowledgeBase()

            # 查询历史教训
            lessons = kb.query_lessons(
                signal_type=opp.signal_type,
                instrument=opp.instrument,
                limit=3
            )

            if not lessons:
                return {"opportunity": opp, "reasons": []}

            adjustment = 0.0
            reasons = []

            for lesson in lessons:
                win_rate = lesson.get("win_rate", 0.5)
                sample_size = lesson.get("sample_size", 0)

                # 样本量太小，不调整
                if sample_size < 5:
                    continue

                # 历史胜率低，降级
                if win_rate < 0.4:
                    adjustment -= 0.2
                    reasons.append(f"历史胜率低({win_rate:.1%}, n={sample_size})，降级-20%")

                # 历史胜率高，升级
                elif win_rate > 0.6:
                    adjustment += 0.1
                    reasons.append(f"历史胜率高({win_rate:.1%}, n={sample_size})，升级+10%")

            # 应用调整
            new_intensity = max(0.0, min(1.0, opp.score.intensity + adjustment))

            # 如果调整后强度过低，拒绝
            if new_intensity < 0.3:
                reasons.append("调整后强度过低，拒绝")
                return None

            opp.score.intensity = new_intensity

            return {"opportunity": opp, "reasons": reasons}

        except Exception as e:
            logger.warning(f"[BranchManager] M8教训调整失败: {e}")
            return {"opportunity": opp, "reasons": []}

    def _apply_m11_validation(self, opp: OpportunityObject) -> Optional[dict]:
        """应用M11 Agent验证"""
        try:
            from m11_agent_sim.agent_network import AgentNetwork
            network = AgentNetwork()

            # 运行M11模拟
            m11_result = network.simulate_realtime(opp)

            opp_direction = opp.direction.value
            m11_consensus = m11_result["consensus_direction"]
            m11_confidence = m11_result["confidence"]

            reasons = []
            downgraded = False

            # 方向一致，通过
            if m11_consensus == opp_direction:
                reasons.append(f"M11共识一致({m11_consensus}, 置信度={m11_confidence:.2f})")
                return {"opportunity": opp, "reasons": reasons, "downgraded": False}

            # 方向冲突且M11高置信度，拒绝
            if m11_confidence > 0.7:
                reasons.append(f"M11高置信度拒绝({m11_consensus}, 置信度={m11_confidence:.2f})")
                return None

            # 方向冲突但M11低置信度，降级
            if m11_confidence > 0.5:
                opp.score.intensity *= 0.7
                reasons.append(f"M11弱冲突({m11_consensus}, 置信度={m11_confidence:.2f})，降级30%")
                downgraded = True

            return {"opportunity": opp, "reasons": reasons, "downgraded": downgraded}

        except Exception as e:
            logger.warning(f"[BranchManager] M11验证失败: {e}")
            return {"opportunity": opp, "reasons": [], "downgraded": False}

    def _open_position_for_branches(
        self,
        opp: OpportunityObject,
        approving_branches: List[dict],
        feed_cls,
    ) -> List[str]:
        """
        为所有认可的分支开仓（实际只开一次）。

        Args:
            opp: 调整后的机会对象（使用最高强度的版本）
            approving_branches: 所有认可的分支信息列表
            feed_cls: 价格数据源类

        Returns:
            position_id列表
        """
        if not self.trader:
            logger.warning("[BranchManager] trader未设置，无法开仓")
            return []

        try:
            from m4_action.action_designer import ActionDesigner

            # M4设计行动计划
            designer = ActionDesigner()
            plan = designer.design(opp)

            # 获取入场价
            feed = feed_cls()
            snap = feed.get_price(opp.instrument)
            if not snap or snap.price <= 0:
                logger.warning(f"[BranchManager] {opp.instrument} 无法获取价格")
                return []

            # 构建metadata
            branch_ids = [b["branch_id"] for b in approving_branches]
            branch_intensities = {b["branch_id"]: b["adjusted_intensity"] for b in approving_branches}

            metadata = {
                "primary_branch": approving_branches[0]["branch_id"],
                "all_approving_branches": branch_ids,
                "branch_intensities": branch_intensities,
                "source": approving_branches[0]["branch"].source,
            }

            # 开仓
            position = self.trader.open_from_plan(
                plan=plan,
                entry_price=snap.price,
                metadata=metadata
            )

            if position:
                # 所有认可的分支都记录开仓
                for branch_info in approving_branches:
                    branch_info["branch"].positions_opened += 1

                logger.info(
                    f"[BranchManager] 开仓: {opp.instrument} @{snap.price:.2f} | "
                    f"分支: {', '.join(branch_ids)} | "
                    f"主分支: {metadata['primary_branch']}"
                )

                return [position.paper_position_id]

            return []

        except Exception as e:
            logger.error(f"[BranchManager] 开仓失败: {e}")
            return []

    def update_branch_metrics(self, closed_position):
        """
        持仓平仓后更新所有相关分支的指标。

        Args:
            closed_position: PaperPosition对象
        """
        metadata = closed_position.metadata or {}
        branch_ids = metadata.get("all_approving_branches", [])

        if not branch_ids:
            # 兼容旧数据：尝试从primary_branch获取
            primary = metadata.get("primary_branch")
            if primary:
                branch_ids = [primary]
            else:
                logger.warning(f"[BranchManager] 持仓 {closed_position.paper_position_id} 无分支信息")
                return

        # 更新所有相关分支的指标
        for branch_id in branch_ids:
            if branch_id not in self.branches:
                logger.warning(f"[BranchManager] 未知分支: {branch_id}")
                continue

            branch = self.branches[branch_id]
            branch.positions_closed += 1
            branch.total_pnl += closed_position.realized_pnl_pct

            if closed_position.realized_pnl_pct > 0:
                branch.win_count += 1

            # 更新平均持仓时长
            hold_hours = (closed_position.close_time - closed_position.entry_time).total_seconds() / 3600
            branch.avg_hold_hours = (
                (branch.avg_hold_hours * (branch.positions_closed - 1) + hold_hours)
                / branch.positions_closed
            )

        logger.info(
            f"[BranchManager] 更新分支指标: {', '.join(branch_ids)} | "
            f"盈亏: {closed_position.realized_pnl_pct:+.2%}"
        )

    def get_branch_report(self, min_closed: int = 1) -> dict:
        """
        生成分支对比报告。

        Args:
            min_closed: 最小平仓数（过滤样本量太小的分支）

        Returns:
            分支报告字典
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_branches": len(self.branches),
            "branches": {}
        }

        for branch_id, branch in sorted(self.branches.items()):
            if branch.positions_closed < min_closed:
                continue

            win_rate = branch.win_count / branch.positions_closed if branch.positions_closed > 0 else 0.0
            avg_pnl = branch.total_pnl / branch.positions_closed if branch.positions_closed > 0 else 0.0

            report["branches"][branch_id] = {
                "config": {
                    "source": branch.source,
                    "sentiment": branch.use_sentiment,
                    "kb": branch.use_knowledge_base,
                    "m11": branch.use_m11_validation,
                },
                "metrics": {
                    "opportunities": branch.total_opportunities,
                    "opened": branch.positions_opened,
                    "closed": branch.positions_closed,
                    "win_rate": round(win_rate, 4),
                    "avg_pnl_pct": round(avg_pnl, 4),
                    "total_pnl_pct": round(branch.total_pnl, 4),
                    "avg_hold_hours": round(branch.avg_hold_hours, 2),
                },
                "filters": {
                    "by_sentiment": branch.filtered_by_sentiment,
                    "by_kb": branch.filtered_by_kb,
                    "by_m11": branch.filtered_by_m11,
                    "downgraded_by_m11": branch.downgraded_by_m11,
                }
            }

        return report

    def save_report(self, report: dict = None):
        """保存分支报告到文件"""
        if report is None:
            report = self.get_branch_report()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self.report_dir / f"branch_report_{timestamp}.json"

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"[BranchManager] 报告已保存: {report_path}")
        return report_path

    def print_summary(self):
        """打印分支摘要（控制台输出）"""
        report = self.get_branch_report(min_closed=1)

        if not report["branches"]:
            print("\n[BranchManager] 暂无足够数据生成报告（需至少1个平仓）")
            return

        print(f"\n{'='*80}")
        print(f"分支对比报告 @ {report['timestamp']}")
        print(f"{'='*80}")

        # 按胜率排序
        sorted_branches = sorted(
            report["branches"].items(),
            key=lambda x: x[1]["metrics"]["win_rate"],
            reverse=True
        )

        for branch_id, data in sorted_branches:
            config = data["config"]
            metrics = data["metrics"]

            print(f"\n[{branch_id}] {config['source']}")
            print(f"  配置: 情绪={config['sentiment']}, 历史={config['kb']}, M11={config['m11']}")
            print(f"  机会: {metrics['opportunities']} → 开仓: {metrics['opened']} → 平仓: {metrics['closed']}")
            print(f"  胜率: {metrics['win_rate']:.1%} | 平均盈亏: {metrics['avg_pnl_pct']:+.2%} | 累计: {metrics['total_pnl_pct']:+.2%}")
            print(f"  持仓时长: {metrics['avg_hold_hours']:.1f}小时")

        print(f"\n{'='*80}\n")
