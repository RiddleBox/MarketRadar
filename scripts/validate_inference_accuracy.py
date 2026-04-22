#!/usr/bin/env python3
"""
验证M3推理引擎准确率
使用2023-2024历史数据，测试推理引擎对降准/降息等事件的预测准确率
目标: 准确率 >= 70%
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timedelta
from typing import List, Dict
from core.schemas import MarketSignal, SignalType, Market, Direction, TimeHorizon, SourceType, SignalLogicFrame
from m2_storage.signal_store import SignalStore
from m3_judgment.judgment_engine import JudgmentEngine
from core.llm_client import LLMClient

# 2023-2024真实事件时间线
GROUND_TRUTH_EVENTS = [
    {
        "event": "2024年2月5日降准0.5个百分点",
        "event_date": datetime(2024, 2, 5),
        "category": "rrr_cut",
        "prior_signals_date": datetime(2024, 1, 24),  # 提前12天的信号日期
        "prior_signals": [
            "国务院常务会议提及'适时降准'",
            "1月CPI同比-0.8%，通缩压力显著",
            "券商普遍预测2月降准概率70%+"
        ]
    },
    {
        "event": "2023年9月15日降准0.25个百分点",
        "event_date": datetime(2023, 9, 15),
        "category": "rrr_cut",
        "prior_signals_date": datetime(2023, 9, 1),  # 提前14天
        "prior_signals": [
            "8月PMI跌破50荣枯线",
            "央行公开市场操作释放宽松信号",
            "多家券商预测9月降准"
        ]
    },
    {
        "event": "2023年6月13日MLF降息10bp",
        "event_date": datetime(2023, 6, 13),
        "category": "rate_cut",
        "prior_signals_date": datetime(2023, 5, 30),  # 提前14天
        "prior_signals": [
            "5月社融数据低于预期",
            "央行行长讲话暗示'保持流动性合理充裕'",
            "市场预期MLF利率下调"
        ]
    },
    {
        "event": "2024年7月22日降息10bp",
        "event_date": datetime(2024, 7, 22),
        "category": "rate_cut",
        "prior_signals_date": datetime(2024, 7, 8),  # 提前14天
        "prior_signals": [
            "三中全会前政策预期升温",
            "6月CPI同比0.2%，通缩风险持续",
            "央行二季度货币政策报告暗示宽松"
        ]
    }
]


def create_signals_from_prior_signals(event: Dict) -> List[MarketSignal]:
    """根据历史事件的前置信号创建MarketSignal对象"""
    signals = []
    base_time = event["prior_signals_date"]

    for i, signal_text in enumerate(event["prior_signals"]):
        # 判断信号类型
        if "国务院" in signal_text or "央行" in signal_text or "讲话" in signal_text:
            signal_type = SignalType.POLICY
            direction = Direction.BULLISH
        elif "CPI" in signal_text or "PMI" in signal_text or "社融" in signal_text:
            signal_type = SignalType.MACRO
            direction = Direction.BEARISH if ("低于" in signal_text or "跌破" in signal_text or "-" in signal_text) else Direction.NEUTRAL
        elif "券商" in signal_text or "预测" in signal_text or "预期" in signal_text:
            signal_type = SignalType.SENTIMENT
            direction = Direction.BULLISH
        else:
            signal_type = SignalType.EVENT_DRIVEN
            direction = Direction.NEUTRAL

        signal = MarketSignal(
            signal_id=f"{event['category']}_{event['event_date'].strftime('%Y%m%d')}_signal_{i+1}",
            signal_type=signal_type,
            signal_label=signal_text[:30],
            description=signal_text,
            evidence_text=signal_text,
            affected_markets=[Market.A_SHARE],
            affected_instruments=[],
            signal_direction=direction,
            event_time=base_time + timedelta(days=i),
            collected_time=base_time + timedelta(days=i),
            time_horizon=TimeHorizon.SHORT,
            intensity_score=8,
            confidence_score=8,
            timeliness_score=9,
            source_type=SourceType.MARKET_DATA,
            source_ref=f"历史记录-{event['event_date'].strftime('%Y%m%d')}",
            logic_frame=SignalLogicFrame(
                what_changed=signal_text,
                change_direction=direction,
                affects=["货币政策", "市场流动性"]
            )
        )
        signals.append(signal)

    return signals


def evaluate_inference_accuracy():
    """评估推理引擎准确率"""
    print("=" * 60)
    print("M3推理引擎准确率验证")
    print("=" * 60)
    print()

    # 初始化组件
    llm_client = LLMClient()
    signal_store = SignalStore()
    judgment_engine = JudgmentEngine(llm_client=llm_client, signal_store=signal_store)

    results = []

    for event in GROUND_TRUTH_EVENTS:
        print(f"\n测试案例: {event['event']}")
        print(f"  实际发生日期: {event['event_date'].strftime('%Y-%m-%d')}")
        print(f"  前置信号日期: {event['prior_signals_date'].strftime('%Y-%m-%d')}")
        print(f"  前置信号:")
        for sig in event['prior_signals']:
            print(f"    - {sig}")

        # 创建信号
        signals = create_signals_from_prior_signals(event)

        # 调用推理引擎
        try:
            inferred_events = judgment_engine._infer_future_events(signals)

            # 检查是否预测到该事件
            predicted = False
            predicted_event = None

            for inf_event in inferred_events:
                event_desc = inf_event.event_description.lower()
                if event['category'] == "rrr_cut" and ("降准" in event_desc or "rrr" in event_desc):
                    predicted = True
                    predicted_event = inf_event
                    break
                elif event['category'] == "rate_cut" and ("降息" in event_desc or "利率" in event_desc):
                    predicted = True
                    predicted_event = inf_event
                    break

            # 计算时间窗口准确性
            time_window_correct = False
            predicted_days = 0
            if predicted and predicted_event:
                # 从time_window字符串解析天数（例："2周内" -> 14天）
                time_window_str = predicted_event.time_window
                if "周" in time_window_str:
                    import re
                    match = re.search(r'(\d+)周', time_window_str)
                    if match:
                        predicted_days = int(match.group(1)) * 7
                elif "天" in time_window_str:
                    import re
                    match = re.search(r'(\d+)天', time_window_str)
                    if match:
                        predicted_days = int(match.group(1))

                actual_days = (event['event_date'] - event['prior_signals_date']).days
                # 允许±5天误差
                if predicted_days > 0 and abs(predicted_days - actual_days) <= 5:
                    time_window_correct = True

            result = {
                "event": event['event'],
                "predicted": predicted,
                "time_window_correct": time_window_correct,
                "predicted_event": predicted_event,
                "actual_days": (event['event_date'] - event['prior_signals_date']).days
            }
            results.append(result)

            print(f"\n  推理结果:")
            print(f"    预测成功: {'是' if predicted else '否'}")
            if predicted and predicted_event:
                print(f"    预测事件: {predicted_event.event_description}")
                print(f"    预测概率: {predicted_event.probability}%")
                print(f"    预测时间窗口: {predicted_event.time_window} ({predicted_days}天)")
                print(f"    实际时间窗口: {result['actual_days']}天")
                print(f"    时间窗口准确: {'是' if time_window_correct else '否'}")

        except Exception as e:
            print(f"  推理失败: {e}")
            results.append({
                "event": event['event'],
                "predicted": False,
                "time_window_correct": False,
                "error": str(e)
            })

    # 计算准确率
    print("\n" + "=" * 60)
    print("准确率统计")
    print("=" * 60)

    total = len(results)
    predicted_correct = sum(1 for r in results if r.get("predicted", False))
    time_window_correct = sum(1 for r in results if r.get("time_window_correct", False))

    event_accuracy = (predicted_correct / total * 100) if total > 0 else 0
    time_accuracy = (time_window_correct / total * 100) if total > 0 else 0

    print(f"\n总测试案例数: {total}")
    print(f"事件预测成功: {predicted_correct}/{total} ({event_accuracy:.1f}%)")
    print(f"时间窗口准确: {time_window_correct}/{total} ({time_accuracy:.1f}%)")
    print(f"\n综合准确率: {event_accuracy:.1f}%")

    if event_accuracy >= 70:
        print("\n[OK] 达到目标准确率 (>=70%)")
    else:
        print(f"\n[FAIL] 未达到目标准确率 (当前{event_accuracy:.1f}% < 70%)")
        print("\n改进建议:")
        print("  1. 增加更多因果模式到causal_patterns表")
        print("  2. 优化LLM评估prompt，提高相似度判断准确性")
        print("  3. 调整概率计算公式，考虑信号强度和时效性")

    return event_accuracy >= 70


if __name__ == "__main__":
    success = evaluate_inference_accuracy()
    sys.exit(0 if success else 1)
