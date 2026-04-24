#!/usr/bin/env python3
"""测试案例库查询"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from m2_storage.case_library import CaseLibraryManager

def main():
    manager = CaseLibraryManager()
    
    # 测试1: 列出所有案例
    print("测试1: 列出所有案例")
    print("="*60)
    all_cases = manager.list_cases()
    print(f"总案例数: {len(all_cases)}")
    for case in all_cases[:5]:
        print(f"  - {case['case_id']}: {case['date_range']}")
    
    # 测试2: 按关键词搜索
    print("\n测试2: 按关键词搜索")
    print("="*60)
    keywords = ["降准", "降息", "政策"]
    for kw in keywords:
        cases = manager.search_cases([kw])
        print(f"  关键词'{kw}': {len(cases)}个案例")
    
    # 测试3: 按信号搜索
    print("\n测试3: 按信号搜索")
    print("="*60)
    signal_keywords = ["央行降息", "政策宽松", "新能源"]
    for kw in signal_keywords:
        cases = manager.search_by_signals([kw])
        print(f"  信号'{kw}': {len(cases)}个案例")
        for case in cases[:2]:
            print(f"    - {case.case_id}: {case.signal_sequence[0][:30]}...")

if __name__ == "__main__":
    main()
