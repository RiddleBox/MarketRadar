#!/usr/bin/env python3
"""
测试实时行情 API（独立版，无需完整依赖）
"""
import requests
from datetime import datetime

# API Keys
ALLTICK_KEY = "1230baa6b4df511826b43549873eecfa-c-app"
ITICK_KEY = "3f9318ac81e449bcb3ccfcf05aaf54910d89268520354dccba95c1c272cd06d6"

# 测试股票
TEST_SYMBOLS = [
    ("600519.SH", "贵州茅台"),
    ("000858.SZ", "五粮液"),
    ("0700.HK", "腾讯控股"),
]

print("🚀 测试实时行情 API")
print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# 测试 iTick
print("=" * 70)
print("测试 iTick（实时）")
print("=" * 70)

for symbol, name in TEST_SYMBOLS:
    code, suffix = symbol.split('.')
    try:
        url = "https://api.itick.org/stock/quote"
        params = {
            "region": suffix,
            "code": code,
            "token": ITICK_KEY,
        }
        
        response = requests.get(url, params=params, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                quote = data.get("data", {})
                price = quote.get("ld", 0)
                change_pct = quote.get("chp", 0)
                print(f"✅ {name:12} ({symbol:12}) | 价格: ¥{price:8.2f} | 涨跌: {change_pct:+6.2f}%")
            else:
                print(f"❌ {name:12} ({symbol:12}) | API错误: {data.get('msg')}")
        else:
            print(f"❌ {name:12} ({symbol:12}) | HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ {name:12} ({symbol:12}) | 错误: {str(e)[:50]}")

print()

# 测试 AllTick
print("=" * 70)
print("测试 AllTick（实时）")
print("=" * 70)

for symbol, name in TEST_SYMBOLS:
    code, suffix = symbol.split('.')
    # AllTick 格式：SH -> SS
    if suffix == 'SH':
        alltick_symbol = f"{code}.SS"
    else:
        alltick_symbol = symbol
    
    try:
        url = "https://quote.tradeswitcher.com/quote-stock-b-api/api/quote/realtime"
        headers = {
            "Authorization": f"Bearer {ALLTICK_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "symbol_list": [alltick_symbol]
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("data") and len(data["data"]) > 0:
                quote = data["data"][0]
                price = quote.get("latest_price", 0)
                change_rate = quote.get("change_rate", 0) * 100
                print(f"✅ {name:12} ({symbol:12}) | 价格: ¥{price:8.2f} | 涨跌: {change_rate:+6.2f}%")
            else:
                print(f"❌ {name:12} ({symbol:12}) | 无数据")
        else:
            print(f"❌ {name:12} ({symbol:12}) | HTTP {response.status_code}: {response.text[:100]}")
    except Exception as e:
        print(f"❌ {name:12} ({symbol:12}) | 错误: {str(e)[:50]}")

print()

# 测试 AKShare
print("=" * 70)
print("测试 AKShare（3-5分钟延迟）")
print("=" * 70)

try:
    import akshare as ak
    
    for symbol, name in TEST_SYMBOLS:
        code, suffix = symbol.split('.')
        
        if suffix in ('SH', 'SZ'):
            try:
                df = ak.stock_zh_a_spot_em()
                row = df[df['代码'] == code]
                
                if not row.empty:
                    price = float(row['最新价'].values[0])
                    change_pct = float(row['涨跌幅'].values[0])
                    print(f"✅ {name:12} ({symbol:12}) | 价格: ¥{price:8.2f} | 涨跌: {change_pct:+6.2f}%")
                else:
                    print(f"❌ {name:12} ({symbol:12}) | 未找到数据")
            except Exception as e:
                print(f"❌ {name:12} ({symbol:12}) | 错误: {str(e)[:50]}")
        else:
            print(f"⚠️  {name:12} ({symbol:12}) | AKShare不支持此市场")
    
except ImportError:
    print("⚠️  akshare 未安装")

print()
print("=" * 70)
print("✅ 测试完成")
print()
print("结论:")
print("  - iTick: 实时数据，免费7天")
print("  - AllTick: 实时数据，免费7天")
print("  - AKShare: 3-5分钟延迟，永久免费")
print()
print("推荐配置: iTick → AllTick → AKShare（自动fallback）")
print("=" * 70)
