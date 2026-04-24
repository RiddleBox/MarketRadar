#!/usr/bin/env python3
"""测试M3案例检索逻辑"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from datetime import datetime, timedelta
from m2_storage.signal_store import SignalStore
from m3_judgment.judgment_engine import JudgmentEngine

def main():
    store = SignalStore()
    engine = JudgmentEngine(signal_store=store)
    
    # 获取最近信号
    end_time = datetime.now()
    start_time = end_time - timedelta(days=7)
    recent_signals = store.get_by_time_range(start_time, end_time)
    
    print(f"最近信号数: {len(recent_signals)}")
    
    # 手动提取标签（模拟M3逻辑）
    tags = []
    for s in recent_signals[:10]:
        print(f"\n信号: {s.signal_label}")
        print(f"  描述: {s.description[:80]}...")
        
        if "降准" in s.signal_label or "降准" in s.description:
            tags.append("降准")
            print("  -> 提取标签: 降准")
        if "降息" in s.signal_label or "降息" in s.description:
            tags.append("降息")
            print("  -> 提取标签: 降息")
        if "政策" in s.signal_label or "政策" in s.description:
            tags.append("政策宽松")
            print("  -> 提取标签: 政策宽松")
        if "通缩" in s.description or "CPI" in s.description:
            tags.append("通缩压力")
            print("  -> 提取标签: 通缩压力")
    
    print(f"\n提取的标签: {set(tags)}")
    
    # 测试查询
    print("\n" + "="*60)
    print("测试案例查询")
    print("="*60)
    
    if tags:
        cases = store.query_similar_cases(tags=list(set(tags)), limit=5)
        print(f"查询结果: {len(cases)}个案例")
        for case in cases:
            print(f"  - {case.case_id}: {case.tags}")
    else:
        print("无标签，跳过查询")

if __name__ == "__main__":
    main()
