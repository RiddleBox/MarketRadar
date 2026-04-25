# -*- coding: utf-8 -*-
"""
实盘信号监控系统
每天自动采集新闻，生成隐性信号，记录验证结果
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import json
import time

sys.path.insert(0, str(Path(__file__).parent))

from llm_config_loader import create_llm_from_config
from m0_collector.providers.xinhua_provider import XinhuaProvider
from m0_collector.providers.ndrc_provider import NDRCProvider
from m0_collector.providers.tech_media_provider import Kr36Provider
from m1_5_implicit_reasoner.inferencer import LLMImplicitSignalInferencer
from m1_5_implicit_reasoner.models import ImplicitSignal
from m2_knowledge_base.industry_graph import IndustryGraph
from m3_reasoning_engine.signal_validator import ImplicitSignalValidator, CaseLibrary
from signal_to_paper_trader import SignalToPaperTrader, create_signal_trader


class LiveSignalMonitor:
    """实盘信号监控器"""

    def __init__(self, output_dir: str = "live_validation", enable_paper_trading: bool = False):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.enable_paper_trading = enable_paper_trading

        # 初始化组件
        print("[初始化] 加载LLM客户端...")
        self.llm_client = create_llm_from_config()

        print("[初始化] 加载产业链图谱...")
        self.industry_graph = IndustryGraph.load_from_file('data/industry_graph_full.json')

        print("[初始化] 加载历史案例库...")
        self.case_library = CaseLibrary()
        with open('data/historical_cases_extended.json', 'r', encoding='utf-8') as f:
            cases_data = json.load(f)
        self.case_library.load_from_dict(cases_data)

        print("[初始化] 初始化推理器和验证器...")
        self.inferencer = LLMImplicitSignalInferencer(
            llm_client=self.llm_client,
            industry_graph=self.industry_graph
        )
        self.validator = ImplicitSignalValidator(self.case_library)

        # 初始化数据源
        print("[初始化] 初始化数据源...")
        self.providers = {
            'xinhua': XinhuaProvider(),
            'ndrc': NDRCProvider(),
            '36kr': Kr36Provider()
        }

        # 初始化模拟盘交易器（如果启用）
        if self.enable_paper_trading:
            print("[初始化] 初始化M9模拟盘交易器...")
            self.signal_trader = create_signal_trader()
        else:
            self.signal_trader = None

        print("[初始化] 完成\n")

    def collect_news(self, date: str = None) -> list:
        """采集当天新闻"""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')

        print(f"[采集] 开始采集 {date} 的新闻...")
        all_news = []

        for provider_name, provider in self.providers.items():
            try:
                print(f"  - {provider_name}...", end=' ')
                news_items = provider.fetch()

                # 转换为字典格式
                today_news = []
                for item in news_items:
                    # 处理 RawArticle 对象
                    if hasattr(item, 'title'):
                        pub_at = getattr(item, 'raw_published_at', '')
                        if pub_at.startswith(date):
                            today_news.append({
                                'title': item.title,
                                'content': item.content,
                                'source': item.source_name,
                                'url': item.source_url,
                                'published_at': pub_at,
                                'provider_id': item.provider_id,
                            })
                    # 处理字典
                    elif isinstance(item, dict):
                        if item.get('published_at', '').startswith(date):
                            today_news.append(item)

                all_news.extend(today_news)
                print(f"获取 {len(today_news)} 条")

            except Exception as e:
                print(f"失败: {e}")

        print(f"[采集] 共获取 {len(all_news)} 条新闻\n")
        return all_news

    def process_news(self, news_items: list) -> tuple:
        """处理新闻，生成隐性信号

        Returns:
            (all_signals, signal_objects) - 信号数据字典列表和ImplicitSignal对象列表
        """
        print(f"[推理] 开始处理 {len(news_items)} 条新闻...")

        all_signals = []
        signal_objects = []  # 保存ImplicitSignal对象用于模拟交易

        for i, news in enumerate(news_items, 1):
            try:
                print(f"\n  [{i}/{len(news_items)}] {news.get('title', 'Unknown')[:50]}...")

                # M1.5推理
                signals = self.inferencer.infer(news)

                if signals:
                    print(f"    识别到 {len(signals)} 个信号")

                    # M3验证
                    for signal in signals:
                        posterior_conf = self.validator.validate(signal)

                        # 保存ImplicitSignal对象
                        signal_objects.append(signal)

                        # 保存验证结果
                        signal_data = {
                            'signal_id': signal.signal_id,
                            'signal_type': signal.signal_type,
                            'source': news.get('source', ''),
                            'title': news.get('title', ''),
                            'published_at': news.get('published_at', ''),
                            'industry_sector': signal.industry_sector,
                            'opportunity_description': signal.opportunity_description,
                            'target_symbols': signal.target_symbols,
                            'prior_confidence': signal.prior_confidence,
                            'posterior_confidence': posterior_conf,
                            'confidence_change': posterior_conf - signal.prior_confidence,
                            'reasoning_chain': {
                                'source_event': signal.reasoning_chain.source_event,
                                'target_opportunity': signal.reasoning_chain.target_opportunity,
                                'causal_links': [
                                    {
                                        'from_concept': link.from_concept,
                                        'to_concept': link.to_concept,
                                        'relation_type': link.relation_type,
                                        'confidence': link.confidence,
                                        'reasoning': link.reasoning
                                    }
                                    for link in signal.reasoning_chain.causal_links
                                ]
                            },
                            'expected_impact_timeframe': signal.expected_impact_timeframe
                        }

                        all_signals.append(signal_data)
                        signal_objects.append(signal)

                        print(f"    - {signal.industry_sector}: {signal.opportunity_description[:40]}...")
                        print(f"      置信度: {signal.prior_confidence:.3f} -> {posterior_conf:.3f} ({posterior_conf - signal.prior_confidence:+.3f})")
                        print(f"      标的: {', '.join(signal.target_symbols[:3])}")
                else:
                    print(f"    未识别到信号")

            except Exception as e:
                print(f"    处理失败: {e}")
                import traceback
                traceback.print_exc()

        print(f"\n[推理] 共生成 {len(all_signals)} 个隐性信号\n")
        return all_signals, signal_objects

    def save_daily_report(self, date: str, news_items: list, signals: list):
        """保存每日报告"""
        report_file = self.output_dir / f"report_{date}.json"

        # 统计信息
        stats = {
            'date': date,
            'news_count': len(news_items),
            'signal_count': len(signals),
            'high_confidence_signals': len([s for s in signals if s['posterior_confidence'] >= 0.7]),
            'signal_types': {},
            'industry_sectors': {}
        }

        for signal in signals:
            # 统计信号类型
            sig_type = signal['signal_type']
            stats['signal_types'][sig_type] = stats['signal_types'].get(sig_type, 0) + 1

            # 统计产业板块
            sector = signal['industry_sector']
            stats['industry_sectors'][sector] = stats['industry_sectors'].get(sector, 0) + 1

        report = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'date': date
            },
            'statistics': stats,
            'signals': signals
        }

        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"[报告] 已保存到 {report_file}")

        # 打印摘要
        print(f"\n{'='*80}")
        print(f"每日信号摘要 - {date}")
        print(f"{'='*80}")
        print(f"新闻数量: {stats['news_count']}")
        print(f"信号数量: {stats['signal_count']}")
        print(f"高置信度信号(>=0.7): {stats['high_confidence_signals']}")

        if stats['signal_types']:
            print(f"\n信号类型分布:")
            for sig_type, count in stats['signal_types'].items():
                print(f"  - {sig_type}: {count}")

        if stats['industry_sectors']:
            print(f"\n产业板块分布:")
            for sector, count in sorted(stats['industry_sectors'].items(), key=lambda x: x[1], reverse=True):
                print(f"  - {sector}: {count}")

        if signals:
            print(f"\n高置信度信号详情:")
            high_conf_signals = sorted(
                [s for s in signals if s['posterior_confidence'] >= 0.7],
                key=lambda x: x['posterior_confidence'],
                reverse=True
            )

            for i, signal in enumerate(high_conf_signals[:5], 1):
                print(f"\n  [{i}] {signal['opportunity_description'][:60]}...")
                print(f"      来源: {signal['source']} - {signal['title'][:50]}...")
                print(f"      板块: {signal['industry_sector']}")
                print(f"      置信度: {signal['posterior_confidence']:.3f}")
                print(f"      标的: {', '.join(signal['target_symbols'][:5])}")
                print(f"      时间框架: {signal['expected_impact_timeframe']}")

        print(f"{'='*80}\n")

    def run_daily_monitoring(self, date: str = None):
        """运行每日监控"""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')

        print(f"\n{'='*80}")
        print(f"实盘信号监控 - {date}")
        print(f"{'='*80}\n")

        # 1. 采集新闻
        news_items = self.collect_news(date)

        if not news_items:
            print("[警告] 未采集到新闻，跳过处理")
            return

        # 2. 处理新闻，生成信号
        signals, signal_objects = self.process_news(news_items)

        # 3. 执行模拟交易（如果启用）
        if self.signal_trader and signal_objects:
            print(f"\n[M9模拟盘] 开始执行交易...")

            # 需要获取当前价格（这里使用模拟价格，实际应该从行情接口获取）
            # TODO: 集成真实行情数据源
            current_prices = {}
            for signal in signal_objects:
                for symbol in signal.target_symbols:
                    # 模拟价格：A股100-300元，港股50-200港币，美股50-500美元
                    if symbol.endswith('.SH') or symbol.endswith('.SZ'):
                        current_prices[symbol] = 150.0
                    elif symbol.endswith('.HK'):
                        current_prices[symbol] = 100.0
                    else:
                        current_prices[symbol] = 200.0

            trade_results = self.signal_trader.process_signals_batch(signal_objects, current_prices)

            print(f"[M9模拟盘] 共创建 {sum(len(v) for v in trade_results.values())} 个持仓")

            # 保存交易结果到报告中
            for signal in signals:
                signal['paper_trade'] = {
                    'position_ids': trade_results.get(signal['signal_id'], []),
                    'position_count': len(trade_results.get(signal['signal_id'], []))
                }

        # 4. 保存报告
        self.save_daily_report(date, news_items, signals)

        print(f"[完成] {date} 的监控任务已完成\n")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='实盘信号监控系统')
    parser.add_argument('--date', type=str, help='指定日期 (YYYY-MM-DD)，默认为今天')
    parser.add_argument('--continuous', action='store_true', help='持续监控模式（每天运行）')
    parser.add_argument('--interval', type=int, default=24, help='持续监控间隔（小时），默认24小时')
    parser.add_argument('--enable-trading', action='store_true', help='启用M9模拟盘交易')

    args = parser.parse_args()

    monitor = LiveSignalMonitor(enable_paper_trading=args.enable_trading)

    if args.enable_trading:
        print("[模式] M9模拟盘交易已启用")

    if args.continuous:
        print(f"[模式] 持续监控模式，每 {args.interval} 小时运行一次")
        print(f"[提示] 按 Ctrl+C 停止监控\n")

        while True:
            try:
                monitor.run_daily_monitoring(args.date)

                print(f"[等待] {args.interval} 小时后执行下一次监控...")
                time.sleep(args.interval * 3600)

            except KeyboardInterrupt:
                print("\n[停止] 用户中断监控")
                break
            except Exception as e:
                print(f"\n[错误] 监控失败: {e}")
                import traceback
                traceback.print_exc()
                print(f"[重试] 1小时后重试...")
                time.sleep(3600)
    else:
        # 单次运行
        monitor.run_daily_monitoring(args.date)


if __name__ == '__main__':
    main()
