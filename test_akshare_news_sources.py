#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试AKShare的各种新闻数据源"""

import sys
import warnings
warnings.filterwarnings('ignore')

# 设置UTF-8输出
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import akshare as ak
import pandas as pd

def test_news_source(name, func, *args):
    """测试单个新闻源"""
    print(f"\n{'='*60}")
    print(f"测试: {name}")
    print('='*60)
    try:
        df = func(*args) if args else func()
        if df is not None and not df.empty:
            print(f"✓ 成功获取 {len(df)} 条数据")
            print(f"列名: {list(df.columns)}")
            print(f"\n前3条数据:")
            print(df.head(3).to_string())
            return True
        else:
            print("✗ 返回空数据")
            return False
    except Exception as e:
        print(f"✗ 失败: {e}")
        return False

# 测试各种新闻源
results = {}

# 1. 百度财经新闻
results['百度财经新闻'] = test_news_source(
    '百度财经新闻 (news_economic_baidu)',
    ak.news_economic_baidu
)

# 2. CCTV新闻
results['CCTV新闻'] = test_news_source(
    'CCTV新闻 (news_cctv)',
    ak.news_cctv
)

# 3. 期货新闻
results['期货新闻'] = test_news_source(
    '上海金属期货新闻 (futures_news_shmet)',
    ak.futures_news_shmet
)

# 4. 测试是否有港股相关新闻
print(f"\n{'='*60}")
print("检查AKShare中与港股/美股相关的API")
print('='*60)
all_funcs = dir(ak)
hk_funcs = [f for f in all_funcs if 'hk' in f.lower() and not f.startswith('_')]
us_funcs = [f for f in all_funcs if ('us' in f.lower() or 'america' in f.lower()) and not f.startswith('_')]

print(f"\n港股相关API ({len(hk_funcs)}个):")
for f in hk_funcs[:10]:
    print(f"  - {f}")

print(f"\n美股相关API ({len(us_funcs)}个):")
for f in us_funcs[:10]:
    print(f"  - {f}")

# 总结
print(f"\n{'='*60}")
print("测试总结")
print('='*60)
for name, success in results.items():
    status = "✓ 可用" if success else "✗ 不可用"
    print(f"{status}: {name}")

print("\n结论:")
print("- AKShare主要提供A股相关新闻（东方财富、财联社等）")
print("- 港股/美股新闻数据源较少，需要其他API补充")
print("- 建议港股使用: 财华社、港交所公告、或英文新闻API")
print("- 建议美股使用: NewsAPI、Finnhub、Alpha Vantage等")
