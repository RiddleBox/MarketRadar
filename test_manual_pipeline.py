#!/usr/bin/env python3
"""
手动输入新闻测试M1→M2→M3流程
用于验证核心逻辑，绕过RSS源失败问题
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from m0_collector.models import RawArticle
from m1_decoder.decoder import SignalDecoder
from core.schemas import SourceType
from m2_storage.signal_store import SignalStore
from m3_judgment.judgment_engine import JudgmentEngine


def create_test_articles():
    """创建测试新闻（模拟降准前置信号）"""
    return [
        RawArticle(
            title="央行行长：将适时降准支持实体经济",
            content="央行行长在国新办发布会上表示，将根据经济形势适时降准，加大对实体经济的支持力度。",
            raw_published_at="2024-01-10 09:30:00",
            source_name="财联社",
            source_url="https://example.com/1",
            provider_id="manual",
            language="zh",
        ),
        RawArticle(
            title="12月CPI同比下降0.3%，PPI同比下降2.7%",
            content="国家统计局公布12月CPI数据，同比下降0.3%，PPI同比下降2.7%，显示通缩压力加大。",
            raw_published_at="2024-01-11 10:00:00",
            source_name="新华社",
            source_url="https://example.com/2",
            provider_id="manual",
            language="zh",
        ),
        RawArticle(
            title="12月PMI为49.0，连续3个月低于荣枯线",
            content="制造业PMI为49.0，连续3个月低于50荣枯线，经济下行压力持续。",
            raw_published_at="2024-01-12 09:00:00",
            source_name="财新网",
            source_url="https://example.com/3",
            provider_id="manual",
            language="zh",
        ),
        RawArticle(
            title="多家券商预测：央行1月下旬可能降准50BP",
            content="中金、中信等多家券商研报预测，央行可能在1月下旬降准50BP，概率超过70%。",
            raw_published_at="2024-01-13 14:00:00",
            source_name="证券时报",
            source_url="https://example.com/4",
            provider_id="manual",
            language="zh",
        ),
    ]


def main():
    print("=" * 80)
    print("Manual Pipeline Test: M1 -> M2 -> M3")
    print("=" * 80)
    print()

    # 1. 创建测试数据
    print("[M0] Creating test articles (simulating RRR cut signals)...")
    articles = create_test_articles()
    print(f"   Total: {len(articles)} articles")
    for i, art in enumerate(articles, 1):
        print(f"   {i}. {art.title}")
    print()

    # 2. M1 解码
    print("[M1] Decoding signals...")
    decoder = SignalDecoder()
    signals = []
    for art in articles:
        sigs = decoder.decode(
            raw_text=art.content,
            source_ref=art.title,
            source_type=SourceType.NEWS,
            batch_id=f"test_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        signals.extend(sigs)
        if sigs:
            print(f"   OK: {art.title[:30]}... -> {len(sigs)} signals")
    print(f"   Total decoded: {len(signals)} signals")
    print()

    # 3. M2 存储
    print("[M2] Storing signals...")
    store = SignalStore()
    saved_count = store.save(signals)
    print(f"   OK: Stored {saved_count} signals")
    print()

    # 4. M3 判断
    print("[M3] Judging opportunities...")
    engine = JudgmentEngine(signal_store=store)

    # 查询最近7天信号
    end_time = datetime.now()
    start_time = end_time - timedelta(days=7)
    recent_signals = store.get_by_time_range(start_time, end_time)
    print(f"   Queried {len(recent_signals)} recent signals")

    # 执行判断
    opportunities = engine.judge(recent_signals)
    print(f"   Identified {len(opportunities)} opportunities")
    print()

    # 5. 输出结果
    if opportunities:
        print("=" * 80)
        print("OPPORTUNITIES FOUND:")
        print("=" * 80)
        for i, opp in enumerate(opportunities, 1):
            print(f"\nOpportunity {i}:")
            print(f"  Title: {opp.opportunity_title}")
            print(f"  Thesis: {opp.opportunity_thesis[:200]}...")
            print(f"  Priority: {opp.priority_level}")
            print(f"  Target Markets: {[m.value for m in opp.target_markets]}")
            print(f"  Direction: {opp.trade_direction}")
            print(f"  Supporting Signals: {len(opp.related_signals)}")
            if opp.inferred_events:
                print(f"  Inferred Events: {len(opp.inferred_events)}")
    else:
        print("WARNING: No opportunities found (causal graph may not match or confidence too low)")

    print()
    print("=" * 80)
    print("Test completed")
    print("=" * 80)


if __name__ == "__main__":
    main()
