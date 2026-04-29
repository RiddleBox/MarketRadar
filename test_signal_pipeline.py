#!/usr/bin/env python3
"""测试信号管道集成"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from run_continuous_simulation import run_signal_pipeline
from pathlib import Path

def test_signal_pipeline():
    """测试信号管道处理"""

    print("=== 测试信号管道 ===\n")

    # 检查测试文件
    test_file = Path("data/incoming/test_news_20260429.txt")
    if not test_file.exists():
        print(f"❌ 测试文件不存在: {test_file}")
        return

    print(f"✓ 测试文件存在: {test_file}")
    print(f"  内容预览: {test_file.read_text(encoding='utf-8')[:100]}...\n")

    # 运行信号管道
    print("运行信号管道...")
    try:
        result = run_signal_pipeline()

        print(f"\n=== 处理结果 ===")
        print(f"  处理文件数: {result['processed_files']}")
        print(f"  生成机会数: {result['total_opportunities']}")

        if result['opportunities']:
            print(f"\n=== 机会详情 ===")
            for i, opp in enumerate(result['opportunities'][:3], 1):
                print(f"\n机会 {i}:")
                print(f"  标题: {opp.opportunity_title}")
                print(f"  标的: {', '.join(opp.target_instruments[:3]) if opp.target_instruments else '待确定'}")
                print(f"  市场: {', '.join([m.value for m in opp.target_markets])}")
                print(f"  方向: {opp.trade_direction.value}")
                print(f"  优先级: {opp.priority_level.value}")
                print(f"  评分: {opp.opportunity_score.overall_score:.2f}")
                print(f"  逻辑: {opp.opportunity_thesis[:100]}...")
                print(f"  来源: {'signal_pipeline' if '_signal' in opp.opportunity_id else 'unknown'}")

        # 检查文件是否被移动到processed
        processed_file = Path("data/processed/test_news_20260429.txt")
        if processed_file.exists():
            print(f"\n✓ 文件已移动到processed目录")
        else:
            print(f"\n⚠ 文件未移动到processed目录")

        print("\n=== 测试完成 ===")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_signal_pipeline()
