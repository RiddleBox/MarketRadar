# -*- coding: utf-8 -*-
"""
signal_to_paper_trader.py - 隐性信号到模拟盘连接器

功能：
1. 从M1.5隐性信号生成ActionPlan
2. 自动提交到M9模拟盘
3. 跟踪信号→交易的映射关系
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict

from core.schemas import (
    ActionPlan, Direction, Market, StopLossConfig, TakeProfitConfig, PositionSizing,
    InstrumentType, PriorityLevel, ActionPhase, ActionType
)
from m1_5_implicit_reasoner.models import ImplicitSignal
from m9_paper_trader import PaperTrader

logger = logging.getLogger(__name__)


class SignalToPaperTrader:
    """隐性信号到模拟盘转换器"""

    def __init__(
        self,
        paper_trader: PaperTrader,
        confidence_threshold: float = 0.65,
        max_position_per_signal: float = 0.05,  # 单个信号最大仓位5%
        default_stop_loss_pct: float = 8.0,     # 默认止损8%
        default_take_profit_pct: float = 15.0,  # 默认止盈15%
    ):
        self.paper_trader = paper_trader
        self.confidence_threshold = confidence_threshold
        self.max_position_per_signal = max_position_per_signal
        self.default_stop_loss_pct = default_stop_loss_pct
        self.default_take_profit_pct = default_take_profit_pct

        # 信号→持仓映射
        self.signal_position_map: Dict[str, List[str]] = {}
        self._load_mapping()

    def process_signal(
        self,
        signal: ImplicitSignal,
        current_prices: Optional[Dict[str, float]] = None,
    ) -> List[str]:
        """
        处理单个隐性信号，生成并提交模拟交易

        Args:
            signal: 隐性信号
            current_prices: 当前价格字典 {symbol: price}

        Returns:
            创建的持仓ID列表
        """
        # 1. 置信度过滤
        if signal.prior_confidence < self.confidence_threshold:
            logger.info(
                f"[SignalTrader] 信号置信度过低 {signal.signal_id}: "
                f"{signal.prior_confidence:.3f} < {self.confidence_threshold}"
            )
            return []

        # 2. 检查是否有明确标的
        if not signal.target_symbols:
            logger.warning(f"[SignalTrader] 信号无目标标的 {signal.signal_id}")
            return []

        # 3. 转换为ActionPlan
        plan = self._signal_to_plan(signal)

        # 4. 获取入场价格
        if not current_prices:
            logger.warning(f"[SignalTrader] 无价格数据，跳过信号 {signal.signal_id}")
            return []

        # 5. 为每个标的创建持仓
        created_positions = []
        for symbol in signal.target_symbols[:3]:  # 最多3个标的
            if symbol not in current_prices:
                logger.warning(f"[SignalTrader] 无价格数据: {symbol}")
                continue

            entry_price = current_prices[symbol]

            # 开立模拟持仓
            positions = self.paper_trader.open_from_plan(
                plan=plan,
                signal_ids=[signal.signal_id],
                opportunity_id=signal.signal_id,
                entry_price=entry_price,
                signal_confidence=signal.prior_confidence,
                signal_type=signal.signal_type,
            )

            for pos in positions:
                created_positions.append(pos.paper_position_id)
                logger.info(
                    f"[SignalTrader] 创建持仓: {symbol} @ {entry_price:.2f} "
                    f"| 信号置信度: {signal.prior_confidence:.3f}"
                )

        # 6. 记录映射关系
        if created_positions:
            self.signal_position_map[signal.signal_id] = created_positions
            self._save_mapping()

        return created_positions

    def process_signals_batch(
        self,
        signals: List[ImplicitSignal],
        current_prices: Optional[Dict[str, float]] = None,
    ) -> Dict[str, List[str]]:
        """
        批量处理信号

        Returns:
            {signal_id: [position_ids]}
        """
        results = {}
        for signal in signals:
            position_ids = self.process_signal(signal, current_prices)
            if position_ids:
                results[signal.signal_id] = position_ids
        return results

    def _signal_to_plan(self, signal: ImplicitSignal) -> ActionPlan:
        """将隐性信号转换为ActionPlan"""
        from datetime import timedelta
        from core.schemas import ActionPhase, InstrumentType, PriorityLevel

        # 推断市场类型
        market = self._infer_market(signal.target_symbols[0] if signal.target_symbols else "")

        # 推断方向（隐性信号通常是利好）
        direction = Direction.BULLISH

        # 根据时间框架调整止损止盈
        stop_loss_pct = self.default_stop_loss_pct
        take_profit_pct = self.default_take_profit_pct

        if signal.expected_impact_timeframe == "immediate":
            # 短期信号：更紧的止损止盈
            stop_loss_pct = 5.0
            take_profit_pct = 10.0
        elif signal.expected_impact_timeframe == "long_term":
            # 长期信号：更宽的止损止盈
            stop_loss_pct = 12.0
            take_profit_pct = 25.0

        # 根据置信度调整仓位
        position_size = self._calculate_position_size(signal.prior_confidence)

        # 创建简单的单阶段行动计划
        phase = ActionPhase(
            phase_name="入场阶段",
            action_type=ActionType.BUY,
            timing_description=f"基于{signal.signal_type}信号，在价格合适时建仓",
            allocation_ratio=1.0,
            trigger_condition="信号置信度达标且价格数据可用"
        )

        # 创建PositionSizing并手动添加数值字段（M9需要）
        position_sizing = PositionSizing(
            suggested_allocation=f"{position_size*100:.1f}%",
            max_allocation=f"{self.max_position_per_signal*100:.1f}%",
            sizing_rationale=f"基于信号置信度 {signal.prior_confidence:.3f}"
        )
        # 手动添加M9需要的数值字段
        position_sizing.suggested_allocation_pct = position_size

        plan = ActionPlan(
            plan_id=f"plan_{signal.signal_id}",
            opportunity_id=signal.signal_id,
            plan_summary=signal.opportunity_description,
            primary_instruments=signal.target_symbols[:3],  # 最多3个标的
            instrument_type=InstrumentType.STOCK,
            direction=direction,
            market=market,
            stop_loss=StopLossConfig(
                stop_loss_type="percent",
                stop_loss_value=stop_loss_pct
            ),
            take_profit=TakeProfitConfig(
                take_profit_type="percent",
                take_profit_value=take_profit_pct
            ),
            position_sizing=position_sizing,
            phases=[phase],
            valid_until=datetime.now() + timedelta(days=30),
            review_triggers=["30日内未入场", "信号失效", "市场环境重大变化"],
            opportunity_priority=PriorityLevel.POSITION
        )

        return plan

    def _infer_market(self, symbol: str) -> Market:
        """推断市场类型"""
        if not symbol:
            return Market.A_SHARE

        if symbol.endswith(".SH") or symbol.endswith(".SZ"):
            return Market.A_SHARE
        elif symbol.endswith(".HK"):
            return Market.HK
        else:
            return Market.US

    def _calculate_position_size(self, confidence: float) -> float:
        """
        根据置信度计算仓位大小

        置信度 0.65-0.75: 2%
        置信度 0.75-0.85: 3%
        置信度 0.85+:     5%
        """
        if confidence >= 0.85:
            return 0.05
        elif confidence >= 0.75:
            return 0.03
        else:
            return 0.02

    def get_signal_positions(self, signal_id: str) -> List[str]:
        """获取信号对应的持仓ID列表"""
        return self.signal_position_map.get(signal_id, [])

    def get_signal_performance(self, signal_id: str) -> Dict:
        """获取信号对应的交易表现"""
        position_ids = self.get_signal_positions(signal_id)
        if not position_ids:
            return {"error": "no positions found"}

        positions = []
        for pos_id in position_ids:
            pos = self.paper_trader.get(pos_id)
            if pos:
                positions.append({
                    "position_id": pos.paper_position_id,
                    "instrument": pos.instrument,
                    "status": pos.status,
                    "entry_price": pos.entry_price,
                    "current_price": pos.current_price,
                    "unrealized_pnl_pct": pos.unrealized_pnl_pct,
                    "realized_pnl_pct": pos.realized_pnl_pct,
                })

        return {
            "signal_id": signal_id,
            "position_count": len(positions),
            "positions": positions,
        }

    def _save_mapping(self):
        """保存信号→持仓映射"""
        mapping_file = Path(__file__).parent / "data" / "signal_position_mapping.json"
        mapping_file.parent.mkdir(parents=True, exist_ok=True)
        mapping_file.write_text(
            json.dumps(self.signal_position_map, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def _load_mapping(self):
        """加载信号→持仓映射"""
        mapping_file = Path(__file__).parent / "data" / "signal_position_mapping.json"
        if mapping_file.exists():
            try:
                self.signal_position_map = json.loads(
                    mapping_file.read_text(encoding="utf-8")
                )
                logger.info(f"[SignalTrader] 加载 {len(self.signal_position_map)} 条信号映射")
            except Exception as e:
                logger.error(f"[SignalTrader] 加载映射失败: {e}")
                self.signal_position_map = {}


def create_signal_trader(
    confidence_threshold: float = 0.65,
    initial_capital: float = 1_000_000,
) -> SignalToPaperTrader:
    """创建信号交易器（便捷函数）"""
    paper_trader = PaperTrader(initial_capital=initial_capital)
    return SignalToPaperTrader(
        paper_trader=paper_trader,
        confidence_threshold=confidence_threshold,
    )


if __name__ == "__main__":
    # 测试示例
    logging.basicConfig(level=logging.INFO)

    # 创建测试信号
    from m1_5_implicit_reasoner.models import ReasoningChain, CausalLink

    test_signal = ImplicitSignal(
        signal_id="test_001",
        signal_type="policy_driven",
        source_event="国家发布半导体产业支持政策",
        industry_sector="半导体设备",
        opportunity_description="政策支持带动半导体设备采购增长",
        target_symbols=["688012.SH", "002371.SZ"],
        reasoning_chain=ReasoningChain(
            source_event="政策支持",
            target_opportunity="设备需求增长",
            causal_links=[
                CausalLink(
                    from_concept="政策支持",
                    to_concept="研发投入",
                    relation_type="policy_drives",
                    confidence=0.9,
                    reasoning="税收减免"
                )
            ]
        ),
        prior_confidence=0.75,
        posterior_confidence=0.78,
        expected_impact_timeframe="mid_term",
        generated_at=datetime.now(),
    )

    # 创建交易器
    trader = create_signal_trader(confidence_threshold=0.65)

    # 模拟价格数据
    prices = {
        "688012.SH": 150.0,
        "002371.SZ": 200.0,
    }

    # 处理信号
    position_ids = trader.process_signal(test_signal, prices)
    print(f"创建持仓: {position_ids}")

    # 查看表现
    performance = trader.get_signal_performance("test_001")
    print(f"信号表现: {json.dumps(performance, ensure_ascii=False, indent=2)}")
