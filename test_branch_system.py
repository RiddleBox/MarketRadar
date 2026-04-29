#!/usr/bin/env python3
"""测试多分支A/B测试系统"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from pipeline.branch_manager import BranchManager
from m12_opportunity_catcher.catcher_engine import OpportunityType
from datetime import datetime

def test_branch_system():
    """测试分支系统的完整流程"""

    print("=== 初始化BranchManager ===")
    branch_mgr = BranchManager()

    # 模拟一个异动机会
    print("\n=== 测试1: M12异动机会 ===")
    anomaly_opp = {
        "symbol": "688981.SH",  # 中芯国际
        "name": "中芯国际",
        "opportunity_type": OpportunityType.PRICE_VOLUME_SURGE.value,
        "signal_strength": 0.85,
        "price": 45.20,
        "volume_ratio": 3.2,
        "price_change_pct": 5.8,
        "detected_at": datetime.now().isoformat(),
        "reason": "成交量放大3.2倍，价格上涨5.8%"
    }

    results = branch_mgr.process_opportunity(anomaly_opp, source="m12_anomaly")
    print(f"\n异动机会处理结果：")
    print(f"  - 生成 {len(results)} 个分支机会")
    for r in results[:3]:  # 只显示前3个
        print(f"  - {r['branch_id']}: 信号强度={r['signal_strength']:.2f}, "
              f"调整={r.get('adjustment_reason', 'N/A')}")

    # 模拟一个信号机会
    print("\n=== 测试2: 信号管道机会 ===")
    signal_opp = {
        "symbol": "688981.SH",
        "name": "中芯国际",
        "opportunity_type": "policy_catalyst",
        "signal_strength": 0.75,
        "price": 45.20,
        "detected_at": datetime.now().isoformat(),
        "reason": "工信部AI芯片扶持政策，利好半导体板块"
    }

    results = branch_mgr.process_opportunity(signal_opp, source="signal_pipeline")
    print(f"\n信号机会处理结果：")
    print(f"  - 生成 {len(results)} 个分支机会")
    for r in results[:3]:
        print(f"  - {r['branch_id']}: 信号强度={r['signal_strength']:.2f}, "
              f"调整={r.get('adjustment_reason', 'N/A')}")

    # 测试重复开仓保护
    print("\n=== 测试3: 重复开仓保护 ===")
    results = branch_mgr.process_opportunity(anomaly_opp, source="m12_anomaly")
    print(f"  - 第二次处理同一标的: {len(results)} 个机会（应该为0）")

    # 显示统计信息
    print("\n=== 分支统计 ===")
    stats = branch_mgr.get_branch_stats()
    for branch_id, stat in list(stats.items())[:4]:  # 只显示前4个
        print(f"{branch_id}: {stat['total_opportunities']}个机会, "
              f"胜率={stat['win_rate']:.1%}, 盈亏={stat['total_pnl']:.2f}")

    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_branch_system()
