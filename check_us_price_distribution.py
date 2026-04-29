#!/usr/bin/env python3
"""检查美股价格分布"""
from futu import OpenQuoteContext, Market as FutuMarket, SecurityType, RET_OK
import numpy as np

quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)

ret, df = quote_ctx.get_stock_basicinfo(
    market=FutuMarket.US,
    stock_type=SecurityType.STOCK
)

if ret == RET_OK and df is not None and not df.empty:
    # 过滤停牌和退市
    df = df[
        (df['suspension'] != 'True') &
        (df['delisting'] == False)
    ]

    print(f'总数: {len(df)} 只')

    # 获取前100只的价格，统计价格分布
    codes = df['code'].head(100).tolist()

    prices = []
    for code in codes[:50]:  # 测试前50只
        try:
            ret2, snap_df = quote_ctx.get_market_snapshot([code])
            if ret2 == RET_OK and not snap_df.empty:
                price = float(snap_df.iloc[0]['last_price'])
                if price > 0:
                    prices.append(price)
        except:
            continue

    if prices:
        prices = np.array(prices)
        print(f'\n采样50只股票的价格分布:')
        print(f'  < $5: {np.sum(prices < 5)} 只 ({np.sum(prices < 5)/len(prices)*100:.1f}%)')
        print(f'  < $10: {np.sum(prices < 10)} 只 ({np.sum(prices < 10)/len(prices)*100:.1f}%)')
        print(f'  < $20: {np.sum(prices < 20)} 只 ({np.sum(prices < 20)/len(prices)*100:.1f}%)')
        print(f'  >= $20: {np.sum(prices >= 20)} 只 ({np.sum(prices >= 20)/len(prices)*100:.1f}%)')
        print(f'\n价格范围: ${prices.min():.2f} - ${prices.max():.2f}')
        print(f'中位数: ${np.median(prices):.2f}')

quote_ctx.close()
