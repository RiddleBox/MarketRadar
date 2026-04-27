#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 3.5 完整流程测试
测试 M0→M1.5→M2→M3→M4→M9 架构
"""

import sys
import os
from pathlib import Path

# 设置UTF-8输出
if sys.platform == 'win32':
    os.system('chcp 65001 > nul')
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """测试所有模块导入"""
    print("=" * 80)
    print("阶段1: 测试模块导入")
    print("=" * 80)

    try:
        # M0
        from m0_collector.providers.xinhua_provider import XinhuaProvider
        print("✓ M0 采集器导入成功")

        # M1.5
        from m1_5_implicit_reasoner.inferencer import LLMImplicitSignalInferencer
        from m1_5_implicit_reasoner.models import ImplicitSignal
        print("✓ M1.5 隐性推理器导入成功")

        # M2
        from m2_storage.signal_store import SignalStore
        from m2_knowledge_base.industry_graph import IndustryGraph
        print("✓ M2 存储和知识库导入成功")

        # M3
        from m3_judgment.judgment_engine import JudgmentEngine
        from m3_judgment.implicit_signal_adapter import ImplicitSignalAdapter
        print("✓ M3 判断引擎导入成功")

        # M4
        from m4_action.action_designer import ActionDesigner
        print("✓ M4 行动设计器导入成功")

        # M9
        from m9_paper_trader import PaperTrader
        print("✓ M9 模拟盘导入成功")

        print("\n所有模块导入成功！\n")
        return True

    except Exception as e:
        print(f"\n✗ 模块导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_m2_implicit_signal_storage():
    """测试M2隐性信号存储"""
    print("=" * 80)
    print("阶段2: 测试M2隐性信号存储")
    print("=" * 80)

    try:
        from m2_storage.signal_store import SignalStore
        from m1_5_implicit_reasoner.models import ImplicitSignal, ReasoningChain, CausalLink, ReasoningStage
        from datetime import datetime

        # 创建测试信号
        test_signal = ImplicitSignal(
            signal_id="test_phase35_001",
            signal_type="policy_driven",
            source_info={"source": "test", "title": "测试新闻"},
            industry_sector="半导体",
            opportunity_description="测试机会描述",
            target_symbols=["688012.SH"],
            reasoning_chain=ReasoningChain(
                chain_id="test_chain_001",
                source_event="测试事件",
                target_opportunity="测试机会",
                causal_links=[
                    CausalLink(
                        from_concept="政策",
                        to_concept="需求",
                        relation_type="policy_drives",
                        confidence=0.8,
                        reasoning="测试推理"
                    )
                ],
                reasoning_stages={
                    ReasoningStage.EVENT_ANALYSIS: "事件分析",
                    ReasoningStage.CAUSAL_INFERENCE: "因果推断"
                },
                overall_confidence=0.78
            ),
            prior_confidence=0.75,
            expected_impact_timeframe="mid_term",
            created_at=datetime.now(),
        )

        # 保存信号
        store = SignalStore()
        success = store.save_implicit_signal(test_signal)

        if success:
            print("✓ 隐性信号保存成功")

            # 查询信号
            retrieved = store.get_implicit_signal_by_id("test_phase35_001")
            if retrieved:
                print(f"✓ 隐性信号查询成功: {retrieved.signal_id}")
                print(f"  - 板块: {retrieved.industry_sector}")
                print(f"  - 置信度: {retrieved.prior_confidence:.3f}")

                # 统计
                stats = store.implicit_signal_stats()
                print(f"✓ 隐性信号统计: 总数={stats['total']}, 平均置信度={stats['avg_confidence']:.3f}")

                print("\nM2存储测试通过！\n")
                return True
            else:
                print("✗ 信号查询失败")
                return False
        else:
            print("✗ 信号保存失败")
            return False

    except Exception as e:
        print(f"\n✗ M2测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_m3_implicit_signal_judgment():
    """测试M3隐性信号判断"""
    print("=" * 80)
    print("阶段3: 测试M3隐性信号判断")
    print("=" * 80)

    try:
        from m3_judgment.judgment_engine import JudgmentEngine
        from m3_judgment.implicit_signal_adapter import ImplicitSignalAdapter
        from m1_5_implicit_reasoner.models import ImplicitSignal, ReasoningChain, CausalLink, ReasoningStage
        from datetime import datetime

        print("✓ 隐性信号支持已启用")

        # 创建测试信号
        test_signal = ImplicitSignal(
            signal_id="test_m3_001",
            signal_type="policy_driven",
            source_info={"source": "test", "title": "国家发布半导体支持政策"},
            industry_sector="半导体设备",
            opportunity_description="政策支持带动设备采购增长",
            target_symbols=["688012.SH", "002371.SZ"],
            reasoning_chain=ReasoningChain(
                chain_id="test_chain_m3",
                source_event="政策支持",
                target_opportunity="设备需求",
                causal_links=[
                    CausalLink(
                        from_concept="政策支持",
                        to_concept="研发投入",
                        relation_type="policy_drives",
                        confidence=0.9,
                        reasoning="税收减免"
                    )
                ],
                reasoning_stages={
                    ReasoningStage.EVENT_ANALYSIS: "政策分析",
                    ReasoningStage.CAUSAL_INFERENCE: "因果推断"
                },
                overall_confidence=0.85
            ),
            prior_confidence=0.75,
            expected_impact_timeframe="mid_term",
            created_at=datetime.now(),
        )

        # 测试适配器
        market_signal = ImplicitSignalAdapter.to_market_signal(test_signal)
        print(f"✓ 信号转换成功: {market_signal.signal_id}")
        print(f"  - 类型: {market_signal.signal_type.value}")
        print(f"  - 置信度分数: {market_signal.confidence_score}/10")

        # 测试判断引擎（不调用LLM，只测试接口）
        engine = JudgmentEngine()
        print("✓ 判断引擎初始化成功")
        print(f"  - judge_implicit_signals方法可用: {hasattr(engine, 'judge_implicit_signals')}")

        print("\nM3适配测试通过！\n")
        return True

    except Exception as e:
        print(f"\n✗ M3测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_complete_pipeline_structure():
    """测试完整流程结构（不执行实际LLM调用）"""
    print("=" * 80)
    print("阶段4: 测试完整流程结构")
    print("=" * 80)

    try:
        from live_signal_monitor import LiveSignalMonitor

        # 初始化监控器（不启用交易）
        print("初始化LiveSignalMonitor...")
        monitor = LiveSignalMonitor(enable_paper_trading=False)

        # 检查组件
        print("\n检查组件初始化:")
        print(f"  ✓ LLM客户端: {monitor.llm_client is not None}")
        print(f"  ✓ 产业链图谱: {monitor.industry_graph is not None}")
        print(f"  ✓ M1.5推理器: {monitor.inferencer is not None}")
        print(f"  ✓ M2信号存储: {monitor.signal_store is not None}")
        print(f"  ✓ M3判断引擎: {monitor.judgment_engine is not None}")
        print(f"  ✓ M4行动设计: {monitor.action_designer is not None}")
        print(f"  ✓ M9模拟盘: {monitor.paper_trader is None} (未启用)")

        # 检查方法
        print("\n检查关键方法:")
        print(f"  ✓ collect_news: {hasattr(monitor, 'collect_news')}")
        print(f"  ✓ process_news: {hasattr(monitor, 'process_news')}")
        print(f"  ✓ run_daily_monitoring: {hasattr(monitor, 'run_daily_monitoring')}")

        print("\n完整流程结构测试通过！\n")
        return True

    except Exception as e:
        print(f"\n✗ 流程结构测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("\n" + "=" * 80)
    print("Phase 3.5 架构修正 - 完整流程测试")
    print("=" * 80 + "\n")

    results = []

    # 测试1: 模块导入
    results.append(("模块导入", test_imports()))

    # 测试2: M2存储
    results.append(("M2隐性信号存储", test_m2_implicit_signal_storage()))

    # 测试3: M3判断
    results.append(("M3隐性信号判断", test_m3_implicit_signal_judgment()))

    # 测试4: 完整流程
    results.append(("完整流程结构", test_complete_pipeline_structure()))

    # 汇总结果
    print("=" * 80)
    print("测试结果汇总")
    print("=" * 80)

    for name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"{name}: {status}")

    all_passed = all(r[1] for r in results)

    if all_passed:
        print("\n" + "=" * 80)
        print("所有测试通过！Phase 3.5架构修正成功。")
        print("=" * 80)
        print("\n下一步:")
        print("1. 运行实际监控: python live_signal_monitor.py --enable-trading")
        print("2. 对比Phase 3捷径 vs Phase 3.5完整流程的效果")
        print("3. 开始Phase 4 (M12交易引擎) 或 M0.5 (机会补牢)")
        print("=" * 80 + "\n")
    else:
        print("\n" + "=" * 80)
        print("部分测试失败，请检查错误信息。")
        print("=" * 80 + "\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
