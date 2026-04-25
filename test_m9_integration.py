# -*- coding: utf-8 -*-
"""
测试M1.5信号到M9模拟盘的完整流程
"""
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from m1_5_implicit_reasoner.models import ImplicitSignal, ReasoningChain, CausalLink, ReasoningStage
from signal_to_paper_trader import create_signal_trader


def test_signal_to_paper_trade():
    """测试信号转换为模拟交易"""
    print("="*80)
    print("测试：M1.5信号 → M9模拟盘")
    print("="*80)

    # 1. 创建测试信号
    print("\n[步骤1] 创建测试信号...")

    # 创建推理链
    reasoning_chain = ReasoningChain(
        chain_id="chain_001",
        source_event="国家发布半导体产业支持政策，提供税收减免和研发补贴",
        target_opportunity="半导体设备采购增长，设备厂商订单增加",
        causal_links=[
            CausalLink(
                from_concept="政策支持",
                to_concept="研发投入增加",
                relation_type="policy_drives",
                confidence=0.9,
                reasoning="税收减免和补贴直接降低研发成本"
            ),
            CausalLink(
                from_concept="研发投入增加",
                to_concept="产能扩张",
                relation_type="investment_leads_to",
                confidence=0.85,
                reasoning="研发投入带动产线建设"
            ),
            CausalLink(
                from_concept="产能扩张",
                to_concept="设备采购",
                relation_type="demand_increase",
                confidence=0.88,
                reasoning="新产线需要采购设备"
            )
        ],
        reasoning_stages={
            ReasoningStage.EVENT_ANALYSIS: "政策支持半导体产业",
            ReasoningStage.CAUSAL_INFERENCE: "政策→研发→产能→设备",
            ReasoningStage.INDUSTRY_IMPACT: "半导体设备行业受益",
            ReasoningStage.TARGET_IDENTIFICATION: "识别设备龙头企业"
        },
        overall_confidence=0.87
    )

    # 创建信号
    test_signal = ImplicitSignal(
        signal_id="test_signal_001",
        signal_type="policy_driven",
        source_info={
            "source": "国家发改委",
            "title": "半导体产业支持政策",
            "url": "https://www.ndrc.gov.cn/test",
            "published_at": datetime.now().isoformat()
        },
        reasoning_chain=reasoning_chain,
        industry_sector="半导体设备",
        target_symbols=["688012.SH", "002371.SZ", "688037.SH"],
        opportunity_description="政策支持带动半导体设备采购增长，设备厂商订单增加",
        prior_confidence=0.82,
        expected_impact_timeframe="mid_term"
    )

    print(f"  信号ID: {test_signal.signal_id}")
    print(f"  信号类型: {test_signal.signal_type}")
    print(f"  置信度: {test_signal.prior_confidence:.3f}")
    print(f"  目标标的: {', '.join(test_signal.target_symbols)}")

    # 2. 创建信号交易器
    print("\n[步骤2] 创建信号交易器...")
    trader = create_signal_trader(
        confidence_threshold=0.65,
        initial_capital=1_000_000
    )
    print(f"  初始资金: 1,000,000")
    print(f"  置信度阈值: 0.65")

    # 3. 模拟价格数据
    print("\n[步骤3] 准备价格数据...")
    current_prices = {
        "688012.SH": 150.50,  # 中微公司
        "002371.SZ": 200.30,  # 北方华创
        "688037.SH": 180.00,  # 芯源微
    }
    for symbol, price in current_prices.items():
        print(f"  {symbol}: {price:.2f}")

    # 4. 处理信号，创建模拟持仓
    print("\n[步骤4] 处理信号，创建模拟持仓...")
    position_ids = trader.process_signal(test_signal, current_prices)

    if position_ids:
        print(f"  [OK] 成功创建 {len(position_ids)} 个持仓")
        for pos_id in position_ids:
            print(f"    - {pos_id}")
    else:
        print(f"  [FAIL] 未创建持仓（可能置信度过低或无价格数据）")
        return

    # 5. 查看持仓详情
    print("\n[步骤5] 查看持仓详情...")
    for pos_id in position_ids:
        pos = trader.paper_trader.get(pos_id)
        if pos:
            print(f"\n  持仓ID: {pos.paper_position_id}")
            print(f"  标的: {pos.instrument}")
            print(f"  方向: {pos.direction}")
            print(f"  入场价: {pos.entry_price:.2f}")
            print(f"  止损价: {pos.stop_loss_price:.2f}")
            print(f"  止盈价: {pos.take_profit_price:.2f}" if pos.take_profit_price else "  止盈价: 未设置")
            print(f"  数量: {pos.quantity:.0f}")
            print(f"  信号置信度: {pos.signal_confidence:.3f}")
            print(f"  状态: {pos.status}")

    # 6. 查看信号表现
    print("\n[步骤6] 查看信号表现...")
    performance = trader.get_signal_performance(test_signal.signal_id)
    print(f"  信号ID: {performance['signal_id']}")
    print(f"  持仓数量: {performance['position_count']}")

    # 7. 模拟价格更新
    print("\n[步骤7] 模拟价格更新...")
    updated_prices = {
        "688012.SH": 155.00,  # +3%
        "002371.SZ": 206.30,  # +3%
        "688037.SH": 185.40,  # +3%
    }

    for symbol, new_price in updated_prices.items():
        print(f"  {symbol}: {current_prices[symbol]:.2f} → {new_price:.2f} ({(new_price/current_prices[symbol]-1)*100:+.2f}%)")

    # 更新持仓价格
    for pos_id in position_ids:
        pos = trader.paper_trader.get(pos_id)
        if pos:
            new_price = updated_prices.get(pos.instrument)
            if new_price:
                pos.update_price(new_price)

    trader.paper_trader._save()

    # 8. 查看更新后的表现
    print("\n[步骤8] 查看更新后的表现...")
    for pos_id in position_ids:
        pos = trader.paper_trader.get(pos_id)
        if pos:
            print(f"\n  {pos.instrument}")
            print(f"  当前价: {pos.current_price:.2f}")
            print(f"  浮动盈亏: {pos.unrealized_pnl_pct*100:+.2f}%")
            print(f"  状态: {pos.status}")

    print("\n" + "="*80)
    print("测试完成")
    print("="*80)


if __name__ == "__main__":
    test_signal_to_paper_trade()
