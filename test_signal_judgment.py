"""
测试信号判断流程 - 诊断为什么没有生成机会

用法:
    python test_signal_judgment.py
"""
from m2_storage.signal_store import SignalStore
from m3_judgment.judgment_engine import JudgmentEngine
from datetime import datetime, timedelta
import json

def main():
    print("=" * 60)
    print("MarketRadar 信号判断诊断工具")
    print("=" * 60)
    print()

    # 1. 加载信号
    print("📊 步骤 1: 加载最近7天的信号...")
    store = SignalStore()
    signals = store.get_by_time_range(
        start=datetime.now() - timedelta(days=7),
        end=datetime.now()
    )

    if not signals:
        print("❌ 没有找到信号")
        return

    print(f"✅ 找到 {len(signals)} 条信号")
    print()

    # 2. 统计信号类型和方向
    print("📈 步骤 2: 分析信号分布...")
    from collections import Counter

    signal_types = Counter([str(s.signal_type) for s in signals])
    signal_directions = Counter([str(s.signal_direction) for s in signals])

    print("信号类型分布:")
    for sig_type, count in signal_types.most_common():
        print(f"  - {sig_type}: {count}")
    print()

    print("信号方向分布:")
    for direction, count in signal_directions.most_common():
        print(f"  - {direction}: {count}")
    print()

    # 3. 分析信号评分
    print("🎯 步骤 3: 分析信号评分...")
    confidence_scores = [s.confidence_score for s in signals if s.confidence_score]
    intensity_scores = [s.intensity_score for s in signals if s.intensity_score]

    if confidence_scores:
        avg_confidence = sum(confidence_scores) / len(confidence_scores)
        max_confidence = max(confidence_scores)
        min_confidence = min(confidence_scores)
        print(f"置信度: 平均={avg_confidence:.2f}, 最高={max_confidence:.2f}, 最低={min_confidence:.2f}")

    if intensity_scores:
        avg_intensity = sum(intensity_scores) / len(intensity_scores)
        max_intensity = max(intensity_scores)
        min_intensity = min(intensity_scores)
        print(f"强度: 平均={avg_intensity:.2f}, 最高={max_intensity:.2f}, 最低={min_intensity:.2f}")
    print()

    # 4. 选择测试信号
    print("🔍 步骤 4: 选择测试信号...")

    # 优先选择评分最高的信号
    test_signals = sorted(
        signals,
        key=lambda s: (s.confidence_score or 0) + (s.intensity_score or 0),
        reverse=True
    )[:3]

    print(f"选择评分最高的 {len(test_signals)} 个信号进行测试:")
    for i, sig in enumerate(test_signals, 1):
        print(f"\n信号 {i}:")
        print(f"  ID: {sig.signal_id}")
        print(f"  类型: {sig.signal_type}")
        print(f"  方向: {sig.signal_direction}")
        print(f"  标签: {sig.signal_label}")
        print(f"  置信度: {sig.confidence_score}")
        print(f"  强度: {sig.intensity_score}")
        print(f"  时效性: {sig.timeliness_score}")
    print()

    # 5. 执行判断测试
    print("⚙️ 步骤 5: 执行判断测试...")
    engine = JudgmentEngine()

    success_count = 0
    for i, test_signal in enumerate(test_signals, 1):
        print(f"\n测试信号 {i}: {test_signal.signal_id}")
        print("-" * 60)

        try:
            opportunity = engine.judge(test_signal)
            success_count += 1

            print(f"✅ 判断成功")
            print(f"  机会ID: {opportunity.opportunity_id}")
            print(f"  优先级: {opportunity.priority_level}")
            print(f"  标题: {opportunity.opportunity_title}")
            print(f"  论点: {opportunity.opportunity_thesis[:100]}...")
            print(f"  目标标的: {', '.join(opportunity.target_instruments[:3])}")
            print(f"  风险收益: {opportunity.risk_reward_profile}")

            # 保存机会到文件
            opp_file = f"data/opportunities/test_opportunity_{opportunity.opportunity_id}.json"
            with open(opp_file, 'w', encoding='utf-8') as f:
                json.dump(opportunity.model_dump(mode='json'), f, ensure_ascii=False, indent=2)
            print(f"  已保存到: {opp_file}")

        except Exception as e:
            print(f"❌ 判断失败: {e}")
            import traceback
            traceback.print_exc()

    print()
    print("=" * 60)
    print(f"测试完成: {success_count}/{len(test_signals)} 个信号成功生成机会")
    print("=" * 60)

    # 6. 诊断建议
    print()
    print("💡 诊断建议:")

    if success_count == 0:
        print("  ⚠️ 所有信号都未能生成机会，可能的原因:")
        print("     1. M3 判断引擎的阈值设置过严")
        print("     2. 信号评分普遍较低")
        print("     3. 信号类型不被 M3 支持")
        print()
        print("  建议操作:")
        print("     1. 检查 config/judgment_config.yaml 中的阈值设置")
        print("     2. 临时降低阈值进行测试")
        print("     3. 查看 M3 判断日志: grep 'M3' data/logs/scheduler.log")

    elif success_count < len(test_signals):
        print(f"  ⚠️ 部分信号未能生成机会 ({success_count}/{len(test_signals)})")
        print("     可能是正常的筛选结果，但建议检查失败的信号特征")

    else:
        print(f"  ✅ 所有测试信号都成功生成机会")
        print("     M3 判断引擎工作正常")
        print("     如果实际运行中没有机会，可能是:")
        print("     1. 信号处理流程未执行")
        print("     2. 信号评分在实际运行中较低")
        print("     3. 调度器配置问题")

if __name__ == "__main__":
    main()
