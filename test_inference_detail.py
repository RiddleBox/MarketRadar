#!/usr/bin/env python3
"""测试推理引擎详细输出"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from datetime import datetime, timedelta
from m2_storage.signal_store import SignalStore
from m3_judgment.judgment_engine import JudgmentEngine

def main():
    store = SignalStore()
    engine = JudgmentEngine(signal_store=store)
    
    # 查询最近信号
    end_time = datetime.now()
    start_time = end_time - timedelta(days=7)
    recent_signals = store.get_by_time_range(start_time, end_time)
    
    print(f"查询到 {len(recent_signals)} 条信号")
    
    # 测试推理引擎
    print("\n" + "="*80)
    print("测试因果链推理")
    print("="*80)
    inferred_events = engine._infer_future_events(recent_signals[:10])
    print(f"\n推理事件数: {len(inferred_events)}")
    for i, event in enumerate(inferred_events, 1):
        print(f"\n事件 {i}:")
        print(f"  描述: {event.event_description}")
        print(f"  概率: {event.probability:.0%}")
        print(f"  时间窗口: {event.time_window}")
        print(f"  置信度: {event.confidence:.0%}")
        print(f"  推理依据: {event.reasoning[:100]}...")
    
    # 测试案例检索
    print("\n" + "="*80)
    print("测试历史案例检索")
    print("="*80)
    similar_cases = engine._retrieve_similar_cases(recent_signals[:10], limit=3)
    print(f"\n相似案例数: {len(similar_cases)}")
    for i, case in enumerate(similar_cases, 1):
        print(f"\n案例 {i}: {case.case_id}")
        print(f"  时间: {case.date_range_start.date()} ~ {case.date_range_end.date()}")
        print(f"  信号: {', '.join(case.signal_sequence[:3])}")
        print(f"  结果: {case.outcome}")
        print(f"  教训: {case.lessons[:100]}...")

if __name__ == "__main__":
    main()
