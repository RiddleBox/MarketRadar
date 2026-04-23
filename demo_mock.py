#!/usr/bin/env python3
"""
实时模拟盘演示（Mock 数据版）

演示完整流程：
  1. 开仓
  2. 价格变化
  3. 止损/止盈触发
"""
import time
import random
from datetime import datetime

print("=" * 70)
print("MarketRadar 实时模拟盘演示（Mock 数据）")
print("=" * 70)
print()

# 初始化
initial_capital = 100000.0
allocation_pct = 0.10

# 测试标的（使用 Mock 价格）
test_symbols = [
    ("510300", "沪深300ETF", 3.850),
    ("159915", "创业板ETF", 2.120),
]

print("📊 初始化...")
print(f"初始资金: ¥{initial_capital:,.2f}")
print(f"单标的仓位: {allocation_pct*100:.0f}%")
print()

# 开仓
print("🔨 开仓...")
positions = []

for code, name, entry_price in test_symbols:
    position_value = initial_capital * allocation_pct
    quantity = int(position_value / entry_price / 100) * 100  # A股最小100股
    
    if quantity < 100:
        print(f"⚠ {name}: 资金不足，跳过")
        continue
    
    stop_loss_price = entry_price * 0.97  # -3% 止损
    take_profit_price = entry_price * 1.05  # +5% 止盈
    
    positions.append({
        'code': code,
        'name': name,
        'entry_price': entry_price,
        'current_price': entry_price,
        'quantity': quantity,
        'stop_loss': stop_loss_price,
        'take_profit': take_profit_price,
        'status': 'OPEN',
    })
    
    print(f"✓ {name}:")
    print(f"  数量: {quantity} 股")
    print(f"  入场: ¥{entry_price:.3f}")
    print(f"  止损: ¥{stop_loss_price:.3f} (-3%)")
    print(f"  止盈: ¥{take_profit_price:.3f} (+5%)")

print()

# 模拟价格变化
print("🔄 模拟价格变化...")
print("   (模拟 30 次更新，每次间隔 1 秒)\n")

update_count = 0
max_updates = 30

try:
    while update_count < max_updates:
        update_count += 1
        print(f"--- 更新 #{update_count} ({datetime.now().strftime('%H:%M:%S')}) ---")
        
        active_count = 0
        for pos in positions:
            if pos['status'] != 'OPEN':
                continue
            
            # 模拟价格变化（随机波动 ±0.5%）
            change_pct = random.uniform(-0.005, 0.005)
            pos['current_price'] = pos['current_price'] * (1 + change_pct)
            
            current_price = pos['current_price']
            pnl_pct = (current_price - pos['entry_price']) / pos['entry_price'] * 100
            
            # 检查止损/止盈
            if current_price <= pos['stop_loss']:
                pos['status'] = 'CLOSED'
                pos['exit_price'] = current_price
                pos['exit_reason'] = 'stop_loss'
                print(f"🛑 {pos['name']}: 止损触发 @ ¥{current_price:.3f} ({pnl_pct:+.2f}%)")
            elif current_price >= pos['take_profit']:
                pos['status'] = 'CLOSED'
                pos['exit_price'] = current_price
                pos['exit_reason'] = 'take_profit'
                print(f"🎯 {pos['name']}: 止盈触发 @ ¥{current_price:.3f} ({pnl_pct:+.2f}%)")
            else:
                active_count += 1
                pnl_symbol = "📈" if pnl_pct > 0 else "📉" if pnl_pct < 0 else "➡️"
                print(f"{pnl_symbol} {pos['name']}: ¥{current_price:.3f} ({pnl_pct:+.2f}%)")
        
        closed_count = len([p for p in positions if p['status'] != 'OPEN'])
        print(f"持仓: {active_count} 活跃 / {closed_count} 已平仓")
        
        if active_count == 0:
            print("\n✅ 所有持仓已平仓，演示结束")
            break
        
        print()
        time.sleep(1)
        
except KeyboardInterrupt:
    print("\n\n⏸️  演示中断")

# 最终报告
print("\n" + "=" * 70)
print("📊 最终报告")
print("=" * 70)

total_pnl = 0
for pos in positions:
    exit_price = pos.get('exit_price', pos['current_price'])
    pnl = (exit_price - pos['entry_price']) * pos['quantity']
    pnl_pct = (exit_price - pos['entry_price']) / pos['entry_price'] * 100
    total_pnl += pnl
    
    status_icon = "✅" if pos['status'] == 'CLOSED' else "⏳"
    print(f"{status_icon} {pos['name']}:")
    print(f"   入场: ¥{pos['entry_price']:.3f}")
    if pos['status'] == 'CLOSED':
        print(f"   出场: ¥{pos['exit_price']:.3f} ({pnl_pct:+.2f}%)")
        print(f"   原因: {pos['exit_reason']}")
    else:
        print(f"   当前: ¥{pos['current_price']:.3f} ({pnl_pct:+.2f}%)")
    print(f"   盈亏: ¥{pnl:+.2f}")

print()
print(f"总盈亏: ¥{total_pnl:+.2f}")
print(f"收益率: {(total_pnl / initial_capital * 100):+.2f}%")
print()

print("=" * 70)
print("✅ 演示完成！")
print()
print("实际使用时：")
print("  1. 替换 Mock 数据为真实行情（AKShare/TuShare/YFinance）")
print("  2. 集成到 M9 PaperTrader 模块")
print("  3. 配置定时任务（每 10 秒更新一次）")
print("  4. 添加 M6 复盘回调")
print("=" * 70)
