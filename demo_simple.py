#!/usr/bin/env python3
"""
实时模拟盘演示（简化版，无需完整依赖）

演示核心逻辑：
  1. 获取实时行情
  2. 计算止损/止盈价格
  3. 模拟价格变化触发
"""
import time
from datetime import datetime

print("=" * 70)
print("MarketRadar 实时模拟盘演示（简化版）")
print("=" * 70)
print()

# 1. 测试 AKShare 实时行情
print("📊 测试 AKShare 实时行情...")
try:
    import akshare as ak
    
    test_symbols = [
        ("510300", "沪深300ETF"),
        ("159915", "创业板ETF"),
    ]
    
    prices = {}
    for code, name in test_symbols:
        try:
            df = ak.stock_zh_a_spot_em()
            row = df[df['代码'] == code]
            if not row.empty:
                price = float(row['最新价'].values[0])
                prices[code] = price
                print(f"✓ {name} ({code}): ¥{price:.3f}")
            else:
                print(f"✗ {name} ({code}): 未找到数据")
        except Exception as e:
            print(f"✗ {name} ({code}): {str(e)[:50]}")
    
    if not prices:
        print("\n❌ 无法获取任何价格数据")
        print("可能原因：")
        print("  1. 非交易时间（A股交易时间：9:30-15:00）")
        print("  2. 网络问题")
        print("  3. AKShare API 变更")
        exit(1)
    
    print()
    
    # 2. 模拟开仓
    print("🔨 模拟开仓...")
    initial_capital = 100000.0
    allocation_pct = 0.10  # 10% 仓位
    
    positions = []
    for code, name in test_symbols:
        if code not in prices:
            continue
        
        entry_price = prices[code]
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
    
    if not positions:
        print("\n❌ 没有成功开仓的持仓")
        exit(1)
    
    print()
    
    # 3. 模拟价格监控
    print("🔄 开始监控价格变化...")
    print("   (按 Ctrl+C 退出)\n")
    
    update_count = 0
    try:
        while True:
            update_count += 1
            print(f"--- 更新 #{update_count} ({datetime.now().strftime('%H:%M:%S')}) ---")
            
            # 获取最新价格
            df = ak.stock_zh_a_spot_em()
            
            active_count = 0
            for pos in positions:
                if pos['status'] != 'OPEN':
                    continue
                
                code = pos['code']
                row = df[df['代码'] == code]
                
                if row.empty:
                    print(f"⚠ {pos['name']}: 无法获取价格")
                    continue
                
                current_price = float(row['最新价'].values[0])
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
            time.sleep(10)  # 每 10 秒更新一次
            
    except KeyboardInterrupt:
        print("\n\n⏸️  演示中断")
    
    # 4. 最终报告
    print("\n" + "=" * 70)
    print("📊 最终报告")
    print("=" * 70)
    
    total_pnl = 0
    for pos in positions:
        exit_price = pos.get('exit_price', pos['entry_price'])
        pnl = (exit_price - pos['entry_price']) * pos['quantity']
        total_pnl += pnl
        
        status_icon = "✅" if pos['status'] == 'CLOSED' else "⏳"
        print(f"{status_icon} {pos['name']}:")
        print(f"   入场: ¥{pos['entry_price']:.3f}")
        if pos['status'] == 'CLOSED':
            print(f"   出场: ¥{pos['exit_price']:.3f}")
            print(f"   原因: {pos['exit_reason']}")
        print(f"   盈亏: ¥{pnl:+.2f}")
    
    print()
    print(f"总盈亏: ¥{total_pnl:+.2f}")
    print(f"收益率: {(total_pnl / initial_capital * 100):+.2f}%")
    print()

except ImportError:
    print("❌ akshare 未安装")
    print("安装命令: pip install --break-system-packages akshare")
except Exception as e:
    print(f"❌ 错误: {e}")
    import traceback
    traceback.print_exc()
