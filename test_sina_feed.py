#!/usr/bin/env python3
"""
测试新浪财经实时行情

对比：
  - 新浪（实时）
  - AKShare（3-5分钟延迟）
"""
import sys
import time
from datetime import datetime

# 测试新浪API
print("=" * 70)
print("测试新浪财经实时行情")
print("=" * 70)
print()

import requests

test_symbols = [
    ("sh600519", "贵州茅台"),
    ("sz000858", "五粮液"),
    ("sh510300", "沪深300ETF"),
]

print("📊 新浪财经 API（实时）:")
for sina_code, name in test_symbols:
    try:
        url = f"http://hq.sinajs.cn/list={sina_code}"
        response = requests.get(url, timeout=3)
        
        if response.status_code == 200:
            content = response.text
            if '""' not in content:
                data_str = content.split('"')[1]
                fields = data_str.split(',')
                
                current_price = float(fields[3])
                prev_close = float(fields[2])
                change_pct = (current_price - prev_close) / prev_close * 100
                volume = float(fields[8])
                
                print(f"✓ {name} ({sina_code}):")
                print(f"  当前价: ¥{current_price:.2f}")
                print(f"  涨跌幅: {change_pct:+.2f}%")
                print(f"  成交量: {volume:.0f}手")
                print(f"  时间: {datetime.now().strftime('%H:%M:%S')}")
            else:
                print(f"⚠ {name} ({sina_code}): 无数据（非交易时间）")
        else:
            print(f"✗ {name} ({sina_code}): HTTP {response.status_code}")
    except Exception as e:
        print(f"✗ {name} ({sina_code}): {str(e)[:50]}")

print()

# 对比 AKShare
print("📊 AKShare（3-5分钟延迟）:")
try:
    import akshare as ak
    
    for sina_code, name in test_symbols:
        # 转换代码格式
        if sina_code.startswith('sh'):
            code = sina_code[2:]
        elif sina_code.startswith('sz'):
            code = sina_code[2:]
        else:
            continue
        
        try:
            df = ak.stock_zh_a_spot_em()
            row = df[df['代码'] == code]
            
            if not row.empty:
                price = float(row['最新价'].values[0])
                change_pct = float(row['涨跌幅'].values[0])
                volume = float(row['成交量'].values[0])
                
                print(f"✓ {name} ({code}):")
                print(f"  当前价: ¥{price:.2f}")
                print(f"  涨跌幅: {change_pct:+.2f}%")
                print(f"  成交量: {volume:.0f}手")
            else:
                print(f"⚠ {name} ({code}): 未找到数据")
        except Exception as e:
            print(f"✗ {name} ({code}): {str(e)[:50]}")
    
except ImportError:
    print("⚠ akshare 未安装")

print()
print("=" * 70)
print("结论:")
print("  - 新浪API: 真正实时，无需注册，但非官方")
print("  - AKShare: 3-5分钟延迟，稳定性一般")
print("  - 建议: 新浪作为主数据源，AKShare作为备用")
print("=" * 70)
