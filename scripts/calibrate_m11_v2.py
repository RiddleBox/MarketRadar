"""
M11 校准脚本 v2 - 基于概率分布的多维度评估

评估指标：
1. 概率校准误差（Brier Score）：模拟概率分布 vs 实际市场反应
2. 极值识别召回率：±5%以上波动的识别能力
3. 情绪分布一致性：模拟情绪强度 vs 实际波动幅度的相关性
4. 方向准确率（参考指标）：仅作为辅助，不作为主要评估标准

设计原则：
- M11任务是模拟市场参与者情绪反应，输出概率分布
- 不追求点预测准确率，追求概率分布校准质量
- 利好出尽、恐慌超跌等逆向反应应体现在概率分布中
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datetime import datetime, timedelta
import numpy as np
from typing import List, Tuple

from m11_agent_sim.schemas import (
    MarketInput, PriceContext, SentimentContext, SignalContext,
    HistoricalEvent, Direction, CalibrationScore, ValidationCase
)
from m11_agent_sim.agent_network import AgentNetwork
from m11_agent_sim.sentiment_provider import DecorrelatedSentimentProvider
from backtest.history_price import HistoryPriceFeed

# 使用相同的标注事件
ANNOTATED_EVENTS = [
    {"date": "2024-09-24", "description": "央行降准降息+政治局会议", "signal_dir": "BULLISH"},
    {"date": "2024-09-26", "description": "证监会放松融资融券", "signal_dir": "BULLISH"},
    {"date": "2024-09-30", "description": "牛市情绪爆发", "signal_dir": "BULLISH"},
    {"date": "2024-10-08", "description": "发改委发布会不及预期", "signal_dir": "BEARISH"},
    {"date": "2024-10-09", "description": "反弹失败", "signal_dir": "BEARISH"},
    {"date": "2024-10-12", "description": "财政部发布会不及预期", "signal_dir": "BEARISH"},
    {"date": "2024-11-08", "description": "万亿国债+地产政策", "signal_dir": "BULLISH"},
    {"date": "2024-11-12", "description": "地产政策不及预期", "signal_dir": "BEARISH"},
    {"date": "2024-11-13", "description": "继续下跌", "signal_dir": "BEARISH"},
    {"date": "2024-11-14", "description": "恐慌加剧", "signal_dir": "BEARISH"},
    {"date": "2024-11-15", "description": "超跌反弹", "signal_dir": "BEARISH"},
    {"date": "2024-12-09", "description": "政治局会议+货币政策", "signal_dir": "BULLISH"},
    {"date": "2024-12-12", "description": "中央经济工作会议", "signal_dir": "BULLISH"},
    {"date": "2024-12-13", "description": "利好出尽", "signal_dir": "BULLISH"},
    {"date": "2024-12-27", "description": "年末资金面紧张", "signal_dir": "BEARISH"},
    {"date": "2025-01-17", "description": "DeepSeek冲击", "signal_dir": "BEARISH"},
]


def calculate_brier_score(predicted_probs: List[Tuple[float, float, float]],
                          actual_directions: List[Direction]) -> float:
    """
    计算Brier Score（概率校准误差）

    Brier Score = (1/N) * Σ[(p_bull - y_bull)² + (p_bear - y_bear)² + (p_neut - y_neut)²]

    y_bull = 1 if actual=BULLISH else 0
    y_bear = 1 if actual=BEARISH else 0
    y_neut = 1 if actual=NEUTRAL else 0

    完美校准: 0.0
    随机猜测: ~0.67
    """
    scores = []
    for (p_bull, p_bear, p_neut), actual in zip(predicted_probs, actual_directions):
        y_bull = 1.0 if actual == "BULLISH" else 0.0
        y_bear = 1.0 if actual == "BEARISH" else 0.0
        y_neut = 1.0 if actual == "NEUTRAL" else 0.0

        score = (p_bull - y_bull)**2 + (p_bear - y_bear)**2 + (p_neut - y_neut)**2
        scores.append(score)

    return np.mean(scores)


def calculate_extreme_recall(simulated_intensities: List[float],
                             actual_returns: List[float],
                             threshold: float = 0.05) -> Tuple[float, int, int]:
    """
    计算极值识别召回率

    极值事件定义：|actual_5d_return| >= threshold（默认5%）
    召回率 = 极值事件中被正确识别的比例（intensity > 7.0）

    返回：(召回率, 识别数, 极值总数)
    """
    extreme_indices = [i for i, r in enumerate(actual_returns) if abs(r) >= threshold]
    if not extreme_indices:
        return 0.0, 0, 0

    identified = sum(1 for i in extreme_indices if simulated_intensities[i] > 7.0)
    return identified / len(extreme_indices), identified, len(extreme_indices)


def calculate_intensity_correlation(simulated_intensities: List[float],
                                    actual_returns: List[float]) -> float:
    """
    计算情绪强度与实际波动幅度的相关性

    理想情况：高强度事件对应大幅波动（正相关或负相关都可以）
    使用绝对收益率，因为强度不区分方向
    """
    abs_returns = [abs(r) for r in actual_returns]
    if len(simulated_intensities) < 2:
        return 0.0

    corr = np.corrcoef(simulated_intensities, abs_returns)[0, 1]
    return corr if not np.isnan(corr) else 0.0


def load_historical_events(price_feed: HistoryPriceFeed,
                          sentiment_provider: DecorrelatedSentimentProvider) -> List[HistoricalEvent]:
    """加载历史事件并计算实际市场反应"""
    events = []

    for evt in ANNOTATED_EVENTS:
        date_str = evt["date"]
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")

        # 获取价格数据（事件日 + 前20日 + 后5日）
        start_date = date_obj - timedelta(days=30)
        end_date = date_obj + timedelta(days=10)
        price_list = price_feed.get_price_range("510300.SH", start_date.date(), end_date.date())

        if not price_list:
            print(f"[WARN] {date_str} 无价格数据，跳过")
            continue

        # 找到事件日的索引
        event_idx = None
        for i, (dt, price) in enumerate(price_list):
            if dt.strftime("%Y-%m-%d") == date_str:
                event_idx = i
                break

        if event_idx is None:
            print(f"[WARN] {date_str} 不在价格数据中，跳过")
            continue

        # 计算实际5日收益（事件日+1 到 事件日+5）
        event_price = price_list[event_idx][1]
        future_prices = [p for _, p in price_list[event_idx+1:event_idx+6]]

        if len(future_prices) < 3:
            print(f"[WARN] {date_str} 后续数据不足，跳过")
            continue

        actual_5d_return = (future_prices[-1] - event_price) / event_price

        # 判断实际方向
        if actual_5d_return > 0.02:
            actual_direction = "BULLISH"
        elif actual_5d_return < -0.02:
            actual_direction = "BEARISH"
        else:
            actual_direction = "NEUTRAL"

        # 构建MarketInput
        price_5d_ago = price_list[max(0, event_idx-5)][1]
        price_20d_ago = price_list[max(0, event_idx-20)][1]
        price_5d_chg = (event_price - price_5d_ago) / price_5d_ago
        price_20d_chg = (event_price - price_20d_ago) / price_20d_ago

        ma5_prices = [p for _, p in price_list[max(0, event_idx-4):event_idx+1]]
        ma20_prices = [p for _, p in price_list[max(0, event_idx-19):event_idx+1]]
        ma5 = sum(ma5_prices) / len(ma5_prices) if ma5_prices else event_price
        ma20 = sum(ma20_prices) / len(ma20_prices) if ma20_prices else event_price

        price_ctx = PriceContext(
            instrument="510300.SH",
            current_price=event_price,
            price_5d_chg_pct=price_5d_chg * 100,
            price_20d_chg_pct=price_20d_chg * 100,
            ma5=ma5,
            ma20=ma20,
            above_ma5=(event_price > ma5),
            above_ma20=(event_price > ma20),
        )

        # 获取情绪数据
        sentiment_ctx = sentiment_provider.get_sentiment(date_obj, evt["signal_dir"])

        # 根据signal_dir设置bullish/bearish_count，ContrarianAgent需要这些字段
        if evt["signal_dir"] == "BULLISH":
            bullish_count, bearish_count = 5, 1
        elif evt["signal_dir"] == "BEARISH":
            bullish_count, bearish_count = 1, 5
        else:
            bullish_count, bearish_count = 2, 2

        signal_ctx = SignalContext(
            dominant_signal_type=evt["signal_dir"],
            bullish_count=bullish_count,
            bearish_count=bearish_count,
            avg_intensity=8.0 if "央行" in evt["description"] or "政治局" in evt["description"] else 6.0,
        )

        market_input = MarketInput(
            timestamp=date_obj,
            market="A_SHARE",
            event_description=evt["description"],
            price=price_ctx,
            sentiment=sentiment_ctx,
            signals=signal_ctx,
        )

        event = HistoricalEvent(
            event_id=f"evt_{date_str}",
            date=date_str,
            description=evt["description"],
            market_input=market_input,
            actual_direction=actual_direction,
            actual_5d_return=actual_5d_return,
            actual_is_extreme=(abs(actual_5d_return) >= 0.05),
        )

        events.append(event)

    return events


def run_calibration(min_confidence: float = 0.50) -> CalibrationScore:
    """运行校准评估"""
    print(f"\n{'='*60}")
    print(f"M11 校准评估 v2 - 概率分布多维度评估")
    print(f"置信度门控: {min_confidence:.0%}")
    print(f"{'='*60}\n")

    # 初始化
    price_feed = HistoryPriceFeed()
    sentiment_provider = DecorrelatedSentimentProvider()
    network = AgentNetwork._default_a_share(min_confidence=min_confidence)

    # 加载历史事件
    events = load_historical_events(price_feed, sentiment_provider)
    print(f"加载 {len(events)} 个历史事件\n")

    # 运行模拟
    predicted_probs = []
    simulated_directions = []
    simulated_intensities = []
    simulated_confidences = []
    actual_directions = []
    actual_returns = []
    cases = []

    for event in events:
        dist = network.run(event.market_input)

        predicted_probs.append((dist.bullish_prob, dist.bearish_prob, dist.neutral_prob))
        simulated_directions.append(dist.direction)
        simulated_intensities.append(dist.intensity)
        simulated_confidences.append(dist.confidence)
        actual_directions.append(event.actual_direction)
        actual_returns.append(event.actual_5d_return)

        direction_match = (dist.direction == event.actual_direction)
        prob_error = abs(dist.bullish_prob - (1.0 if event.actual_direction == "BULLISH" else 0.0))

        case = ValidationCase(
            event_id=event.event_id,
            date=event.date,
            description=event.description,
            actual_direction=event.actual_direction,
            simulated_direction=dist.direction,
            direction_match=direction_match,
            actual_5d_return=event.actual_5d_return,
            simulated_bullish_prob=dist.bullish_prob,
            prob_error=prob_error,
            simulated_intensity=dist.intensity,
            simulated_confidence=dist.confidence,
        )
        cases.append(case)

        match_icon = "OK" if direction_match else "MISS"
        print(f"{match_icon} {event.date} {event.description[:20]:20s} | "
              f"实际:{event.actual_direction:8s} ({event.actual_5d_return:+.1%}) | "
              f"模拟:{dist.direction:8s} 多{dist.bullish_prob:.0%}/空{dist.bearish_prob:.0%}/震{dist.neutral_prob:.0%} "
              f"强度{dist.intensity:.1f} 置信{dist.confidence:.0%}")

    # 计算评估指标
    print(f"\n{'='*60}")
    print("评估指标")
    print(f"{'='*60}\n")

    # 1. Brier Score（概率校准误差）
    brier_score = calculate_brier_score(predicted_probs, actual_directions)
    print(f"1. Brier Score（概率校准误差）: {brier_score:.4f}")
    print(f"   - 完美校准: 0.0")
    print(f"   - 随机猜测: ~0.67")
    print(f"   - 合格标准: < 0.50")
    print(f"   - 当前评级: {'PASS' if brier_score < 0.50 else 'FAIL'}\n")

    # 2. 极值识别召回率
    recall, identified, total_extreme = calculate_extreme_recall(simulated_intensities, actual_returns)
    print(f"2. 极值识别召回率（±5%以上波动）: {recall:.1%}")
    print(f"   - 极值事件总数: {total_extreme}")
    print(f"   - 正确识别数: {identified}")
    print(f"   - 目标标准: ≥ 60%")
    print(f"   - 当前评级: {'PASS' if recall >= 0.60 else 'FAIL'}\n")

    # 3. 情绪强度-波动幅度相关性
    intensity_corr = calculate_intensity_correlation(simulated_intensities, actual_returns)
    print(f"3. 情绪强度-波动幅度相关性: {intensity_corr:.3f}")
    print(f"   - 目标标准: > 0.30（中等相关）")
    print(f"   - 当前评级: {'PASS' if intensity_corr > 0.30 else 'FAIL'}\n")

    # 4. 方向准确率（参考指标）
    direction_hits = sum(1 for s, a in zip(simulated_directions, actual_directions) if s == a)
    direction_accuracy = direction_hits / len(events)

    selective_cases = [c for c in cases if c.simulated_direction != "NEUTRAL"]
    selective_hits = sum(1 for c in selective_cases if c.direction_match)
    selective_accuracy = selective_hits / len(selective_cases) if selective_cases else 0.0
    skip_rate = 1.0 - len(selective_cases) / len(cases)

    print(f"4. 方向准确率（参考指标，非主要评估标准）:")
    print(f"   - 总体准确率: {direction_accuracy:.1%} ({direction_hits}/{len(events)})")
    print(f"   - 选择性准确率: {selective_accuracy:.1%} ({selective_hits}/{len(selective_cases)})")
    print(f"   - 跳过率: {skip_rate:.1%}\n")

    # 综合评分
    # 权重：Brier Score 40%，极值召回率 30%，强度相关性 20%，方向准确率 10%
    brier_score_normalized = max(0, 1 - brier_score / 0.67)  # 归一化到[0,1]
    composite_score = (
        brier_score_normalized * 0.40 +
        recall * 0.30 +
        max(0, intensity_corr) * 0.20 +
        direction_accuracy * 0.10
    ) * 100

    pass_threshold = (brier_score < 0.50 and recall >= 0.60 and intensity_corr > 0.30)

    print(f"{'='*60}")
    print(f"综合评分: {composite_score:.1f}/100")
    print(f"准入判定: {'PASS' if pass_threshold else 'FAIL'}")
    print(f"{'='*60}\n")

    score = CalibrationScore(
        total_events=len(events),
        direction_hits=direction_hits,
        direction_accuracy=direction_accuracy,
        prob_calibration_err=brier_score,
        extreme_recall=recall,
        composite_score=composite_score,
        pass_threshold=pass_threshold,
        selective_accuracy=selective_accuracy,
        selective_n=len(selective_cases),
        skip_rate=skip_rate,
    )

    return score


if __name__ == "__main__":
    score = run_calibration(min_confidence=0.50)
