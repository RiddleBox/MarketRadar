#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整流程演示：M0→M1→M2→M3
使用模拟新闻数据，展示系统如何生成投资机会
"""
import sys
import os
from datetime import datetime
from pathlib import Path

# Windows控制台UTF-8编码
if sys.platform == 'win32':
    os.system('chcp 65001 > nul')
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent))

from m0_collector.models import RawArticle, CollectedItem
from m0_collector.dedup import DedupIndex
from m0_collector.normalizer import Normalizer
from m1_decoder.decoder import SignalDecoder
from m2_storage.signal_store import SignalStore
from m3_judgment.judgment_engine import JudgmentEngine
from core.schemas import SourceType, Market
import uuid

def main():
    print("=" * 80)
    print("MarketRadar 完整流程演示")
    print("=" * 80)

    # 模拟新闻数据
    mock_news = [
        {
            "title": "央行宣布降准0.5个百分点 释放长期资金约1万亿元",
            "content": "中国人民银行决定于2026年4月25日下调金融机构存款准备金率0.5个百分点，此次降准将释放长期资金约1万亿元。央行表示，此举旨在保持流动性合理充裕，支持实体经济发展。",
            "source": "中国人民银行",
            "url": "http://www.pbc.gov.cn/news/2026/04/24/001.html",
        },
        {
            "title": "12月CPI同比下降0.3% 通缩压力显现",
            "content": "国家统计局公布，12月CPI同比下降0.3%，环比下降0.5%。PPI同比下降2.7%，连续15个月负增长。分析认为，需求不足导致价格持续低迷。",
            "source": "国家统计局",
            "url": "http://www.stats.gov.cn/news/2026/04/24/002.html",
        },
        {
            "title": "12月PMI为49.0 连续3个月低于荣枯线",
            "content": "制造业PMI为49.0，连续3个月位于收缩区间。新订单指数48.5，生产指数49.8，均低于临界点。经济下行压力加大。",
            "source": "国家统计局",
            "url": "http://www.stats.gov.cn/news/2026/04/24/003.html",
        },
        {
            "title": "新能源汽车购置税减免政策延续至2027年",
            "content": "财政部、税务总局联合发布公告，新能源汽车购置税减免政策延续至2027年底。业内预计此举将提振新能源汽车销量。",
            "source": "财政部",
            "url": "http://www.mof.gov.cn/news/2026/04/24/004.html",
        },
        {
            "title": "某半导体龙头Q1业绩预增150%-180%",
            "content": "某半导体公司发布业绩预告，预计Q1净利润同比增长150%-180%，主要受益于AI芯片需求爆发和产能利用率提升。",
            "source": "上交所",
            "url": "http://www.sse.com.cn/news/2026/04/24/005.html",
        },
    ]

    # M0: 数据采集与标准化
    print("\n[M0] 数据采集与标准化")
    print("-" * 80)

    raw_articles = []
    for news in mock_news:
        article = RawArticle(
            title=news["title"],
            content=news["content"],
            raw_published_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            source_name=news["source"],
            source_url=news["url"],
            provider_id="manual",
            language="zh",
        )
        raw_articles.append(article)

    print(f"✓ 采集到 {len(raw_articles)} 篇新闻")

    # 标准化
    dedup = DedupIndex()
    normalizer = Normalizer(dedup_index=dedup)
    normalized = normalizer.normalize(raw_articles)

    # 展平（normalizer返回的是嵌套列表）
    all_items = []
    for item in normalized:
        if isinstance(item, list):
            all_items.extend(item)
        elif hasattr(item, 'title'):  # 是CollectedItem对象
            all_items.append(item)

    print(f"✓ 标准化后 {len(all_items)} 条")

    # M1: 信号解码
    print("\n[M1] 信号解码")
    print("-" * 80)

    decoder = SignalDecoder()
    all_signals = []
    batch_id = f"demo_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    for item in all_items:
        signals = decoder.decode(
            raw_text=item.title + " " + item.content,
            source_ref=item.source_url,
            source_type=SourceType.NEWS,
            batch_id=batch_id,
        )
        all_signals.extend(signals)
        print(f"  {item.title[:50]}... -> {len(signals)} 个信号")

    print(f"\n✓ 总共解码出 {len(all_signals)} 个信号")

    # M2: 信号存储
    print("\n[M2] 信号存储")
    print("-" * 80)

    store = SignalStore()
    saved = store.save(all_signals)
    print(f"✓ 存储了 {saved} 个信号")

    stats = store.stats()
    print(f"✓ 数据库统计: 总计 {stats['total']} 条信号")

    # M3: 机会判断
    print("\n[M3] 机会判断")
    print("-" * 80)

    engine = JudgmentEngine()
    opportunities = engine.judge(
        signals=all_signals,
        batch_id=batch_id,
    )

    print(f"✓ 识别出 {len(opportunities)} 个投资机会")

    # 输出机会详情
    if opportunities:
        print("\n" + "=" * 80)
        print("投资机会详情")
        print("=" * 80)

        for i, opp in enumerate(opportunities, 1):
            print(f"\n【机会 {i}】{opp.opportunity_title}")
            print(f"方向: {opp.trade_direction.value}")
            print(f"优先级: {opp.priority_level.value}")
            print(f"目标市场: {', '.join([m.value for m in opp.target_markets])}")
            print(f"相关信号数: {len(opp.related_signals)}")
            print(f"推断事件数: {len(opp.inferred_events)}")
            print(f"\n投资逻辑:")
            thesis = opp.opportunity_thesis
            print(thesis[:300] + "..." if len(thesis) > 300 else thesis)
    else:
        print("\n⚠ 当前信号未形成明确的投资机会")

    print("\n" + "=" * 80)
    print("✅ 完整流程演示完成！")
    print("=" * 80)

if __name__ == "__main__":
    main()
