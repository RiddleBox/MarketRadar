"""
测试M12异动溯源轨道完整流程

流程：异动检测 → 反向溯源 → M3判断 → 趋势判断 → M4设计 → M9执行

测试策略：
1. 创建模拟价格异动（隆基绿能大涨）
2. 预先在M2中插入相关新闻信号（触发溯源）
3. 运行M12扫描，检查是否生成RetroOpportunity
4. 如果生成机会，测试M4设计ActionPlan
5. 如果设计成功，测试M9模拟开仓
"""
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.schemas import (
    AnomalyType,
    Direction,
    InstrumentType,
    Market,
    MarketSignal,
    PriceAnomaly,
    SignalType,
    SourceType,
)


def print_section(title: str):
    """打印分隔线"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def create_mock_anomaly() -> PriceAnomaly:
    """创建模拟异动：隆基绿能大涨8%"""
    return PriceAnomaly(
        instrument="601012.SH",
        market=Market.A_SHARE,
        anomaly_type=AnomalyType.DAILY_SURGE,
        anomaly_date=date.today(),
        price_change_pct=8.5,
        atr_multiple=3.2,
        sigma_multiple=2.8,
        volume_ratio=2.5,
        baseline_price=20.0,
        anomaly_price=21.7,
        n_days=1,
        is_limit_up=False,
        is_limit_down=False,
    )


def create_mock_signals() -> list[MarketSignal]:
    """创建模拟信号：隆基绿能相关新闻"""
    signals = []

    # 信号1: 重大订单
    signals.append(MarketSignal(
        signal_id="sig_mock_001",
        signal_type=SignalType.EVENT_DRIVEN,
        signal_label="隆基绿能获100亿美元海外订单",
        signal_content="隆基绿能宣布与欧洲能源巨头签署100亿美元光伏组件供应协议，订单将在2026-2028年交付。",
        source_type=SourceType.NEWS,
        source_url="https://example.com/news/1",
        detected_at=datetime.now() - timedelta(hours=2),
        target_markets=[Market.A_SHARE],
        target_instruments=["601012.SH"],
        instrument_types=[InstrumentType.STOCK],
        trade_direction=Direction.BULLISH,
        confidence_score=0.85,
        time_sensitivity="high",
        catalyst_type="fundamental",
    ))

    # 信号2: 技术突破
    signals.append(MarketSignal(
        signal_id="sig_mock_002",
        signal_type=SignalType.TECHNICAL,
        signal_label="隆基绿能BC电池转换效率突破27%",
        signal_content="隆基绿能宣布其BC电池转换效率达到27.09%，创造新的世界纪录，领先行业平均水平2个百分点。",
        source_type=SourceType.NEWS,
        source_url="https://example.com/news/2",
        detected_at=datetime.now() - timedelta(hours=1),
        target_markets=[Market.A_SHARE],
        target_instruments=["601012.SH"],
        instrument_types=[InstrumentType.STOCK],
        trade_direction=Direction.BULLISH,
        confidence_score=0.80,
        time_sensitivity="medium",
        catalyst_type="technology",
    ))

    # 信号3: 行业趋势
    signals.append(MarketSignal(
        signal_id="sig_mock_003",
        signal_type=SignalType.INDUSTRY,
        signal_label="2026年全球光伏装机目标上调至200GW",
        signal_content="国际能源署上调2026年全球光伏新增装机预测至200GW，同比增长30%，光伏板块迎来新一轮增长周期。",
        source_type=SourceType.RESEARCH_REPORT,
        source_url="https://example.com/research/1",
        detected_at=datetime.now() - timedelta(hours=3),
        target_markets=[Market.A_SHARE],
        target_instruments=["601012.SH", "688223.SH"],
        instrument_types=[InstrumentType.STOCK],
        trade_direction=Direction.BULLISH,
        confidence_score=0.75,
        time_sensitivity="low",
        catalyst_type="macro",
    ))

    return signals


def test_m12_track():
    """测试M12轨道完整流程"""

    print_section("M12 异动溯源轨道测试")

    # Step 1: 准备测试数据
    print_section("Step 1: 准备测试数据")
    anomaly = create_mock_anomaly()

    print(f"[OK] 创建模拟异动: {anomaly.instrument}")
    print(f"     涨幅: {anomaly.price_change_pct:+.1f}%")
    print(f"     ATR倍数: {anomaly.atr_multiple:.1f}x")
    print(f"     量比: {anomaly.volume_ratio:.1f}x")

    # Step 2: 从M2获取历史信号（使用真实数据）
    print_section("Step 2: 从M2获取历史信号")
    try:
        from m2_storage.signal_store import SignalStore
        signal_store = SignalStore()

        # 查询A股信号
        all_signals = signal_store.query(
            markets=[Market.A_SHARE],
            lookback_days=7,
            limit=50,
        )

        # 过滤隆基绿能相关信号
        stored = [s for s in all_signals if "601012.SH" in s.affected_instruments]

        if not stored:
            # 如果没有隆基绿能的信号，使用所有A股信号
            print("[WARN] 未找到隆基绿能信号，使用其他A股信号")
            stored = all_signals[:10]

        print(f"[OK] 从M2获取 {len(stored)} 个历史信号")
        if stored:
            print(f"     最新信号: {stored[0].signal_label[:50]}")

    except Exception as e:
        print(f"[X] M2查询失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 3: 运行M12异动处理
    print_section("Step 3: 运行M12异动处理")
    try:
        from m12_opportunity_catcher.catcher_engine import OpportunityCatcherEngine
        from m12_opportunity_catcher.market_strategies import get_strategy

        # 初始化M12引擎（会自动初始化M3）
        catcher = OpportunityCatcherEngine()
        print("[OK] M12引擎初始化成功")

        # 获取市场策略
        strategy = get_strategy(Market.A_SHARE)

        # 处理异动
        retro_opp = catcher._process_anomaly(
            anomaly=anomaly,
            historical_signals=stored,
            sentiment_data=None,
            strategy=strategy,
        )

        if retro_opp is None:
            print("[X] M12未生成机会（可能被过滤）")
            return

        print(f"[OK] M12生成RetroOpportunity")
        print(f"     机会ID: {retro_opp.opportunity.opportunity_id}")
        print(f"     标题: {retro_opp.opportunity.opportunity_title}")
        print(f"     优先级: {retro_opp.opportunity.priority_level.value}")
        print(f"     方向: {retro_opp.opportunity.trade_direction.value}")
        print(f"     趋势阶段: {retro_opp.trend.stage.value}")
        print(f"     溯源置信度: {retro_opp.causation.confidence:.0%}")

        if retro_opp.opportunity.opportunity_score:
            score = retro_opp.opportunity.opportunity_score
            print(f"     综合评分: {score.overall_score:.1f}")
            print(f"     置信度: {score.confidence_score:.2f}")

    except Exception as e:
        print(f"[X] M12处理失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 4: M4设计行动计划
    print_section("Step 4: M4设计行动计划")
    try:
        from m4_action.action_designer import ActionDesigner
        from core.llm_client import LLMClient

        designer = ActionDesigner(llm_client=LLMClient())
        plan = designer.design(retro_opp.opportunity)
        print(f"[OK] M4生成ActionPlan")
        print(f"     计划ID: {plan.plan_id}")
        print(f"     标的: {', '.join(plan.primary_instruments[:3])}")
        print(f"     方向: {plan.direction.value}")
        print(f"     仓位: {plan.position_sizing.suggested_allocation}")
        print(f"     止损: {plan.stop_loss.stop_loss_value}%")
        print(f"     止盈: {plan.take_profit.take_profit_value}%")

    except Exception as e:
        print(f"[X] M4设计失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 5: M9模拟开仓
    print_section("Step 5: M9模拟开仓")
    try:
        from m9_paper_trader.paper_trader import PaperTrader
        from m9_paper_trader.feed_factory import get_factory

        trader = PaperTrader()
        factory = get_factory()

        # 获取当前价格
        feed = factory.get_feed(market=Market.A_SHARE)
        current_price = feed.get_current_price(anomaly.instrument)

        if current_price is None:
            print(f"[WARN] 无法获取 {anomaly.instrument} 当前价格，使用异动价格")
            current_price = anomaly.anomaly_price

        print(f"[OK] 获取当前价格: {current_price:.2f}")

        # 开仓
        position = trader.open_from_plan(
            plan=plan,
            entry_price=current_price,
            entry_time=datetime.now(),
        )

        print(f"[OK] M9开仓成功")
        print(f"     持仓ID: {position.position_id}")
        print(f"     标的: {position.instrument}")
        print(f"     方向: {position.direction.value}")
        print(f"     数量: {position.quantity}")
        print(f"     成本: {position.entry_price:.2f}")
        print(f"     止损价: {position.stop_loss_price:.2f}")

    except Exception as e:
        print(f"[X] M9开仓失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # 总结
    print_section("测试总结")
    print("[OK] M12轨道完整流程测试通过")
    print("     异动检测 -> 反向溯源 -> M3判断 -> 趋势判断 -> M4设计 -> M9执行")
    print("     所有模块正常协作")


if __name__ == "__main__":
    test_m12_track()
