"""
scripts/run_llm_calibration.py — M11 LLM Mode Calibration

Uses DeepSeek (or configured provider) to re-run historical events
through AgentNetwork in LLM mode, comparing results against rule-based mode.

This is Iteration 10.1: the most critical improvement for M11 admission.

Usage:
    python scripts/run_llm_calibration.py
    python scripts/run_llm_calibration.py --provider deepseek
    python scripts/run_llm_calibration.py --provider auto --min-events 30
    python scripts/run_llm_calibration.py --dry-run  (rule-based only, no LLM calls)
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(ROOT / "logs" / "llm_calibration.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def run_calibration(
    provider: str = "deepseek",
    min_events: int = 50,
    dry_run: bool = False,
    topology: str = "sequential",
):
    from m11_agent_sim.agent_network import AgentNetwork
    from m11_agent_sim.calibrator import HistoricalCalibrator
    from m11_agent_sim.event_catalog import load_event_catalog
    from m11_agent_sim.calibration_store import CalibrationStore

    events = load_event_catalog(min_events=min_events)
    logger.info(f"Loaded {len(events)} events from catalog")

    rule_network = AgentNetwork._default_a_share(topology=topology, use_llm=False)
    rule_calibrator = HistoricalCalibrator(network=rule_network)
    logger.info("Running RULE-BASED calibration...")
    rule_score = rule_calibrator.calibrate(events, persist=True)
    logger.info(
        f"Rule-based result: direction_accuracy={rule_score.direction_accuracy:.2%} "
        f"composite={rule_score.composite_score:.1f} "
        f"pass={rule_score.pass_threshold}"
    )

    if dry_run:
        logger.info("DRY RUN: skipping LLM calibration")
        _print_comparison(rule_score, None)
        return rule_score, None

    from integrations.llm_adapter import make_llm_client
    llm_client = make_llm_client(provider=provider, fallback_to_rules=False)
    if llm_client is None:
        logger.error("No LLM client available, aborting")
        return rule_score, None

    logger.info(f"LLM client ready: {llm_client}")

    llm_network = AgentNetwork._default_a_share(
        topology=topology, llm_client=llm_client, use_llm=True
    )
    llm_calibrator = HistoricalCalibrator(network=llm_network)

    logger.info("Running LLM calibration (this may take a while with rate limits)...")
    t0 = time.time()
    llm_score = _calibrate_with_retry(llm_calibrator, events)
    elapsed = time.time() - t0
    logger.info(f"LLM calibration completed in {elapsed:.0f}s")

    logger.info(
        f"LLM result: direction_accuracy={llm_score.direction_accuracy:.2%} "
        f"composite={llm_score.composite_score:.1f} "
        f"pass={llm_score.pass_threshold}"
    )

    _print_comparison(rule_score, llm_score)

    report = _build_report(rule_score, llm_score, events, provider, elapsed)
    _save_report(report)

    store = CalibrationStore()
    runs = store.list_runs(limit=5)
    logger.info(f"Calibration history ({len(runs)} runs):")
    for r in runs:
        logger.info(
            f"  {r['run_id']}: accuracy={r['direction_accuracy']:.2%} "
            f"composite={r['composite_score']:.1f} "
            f"pass={bool(r['pass_threshold'])}"
        )

    return rule_score, llm_score


def _calibrate_with_retry(calibrator, events, max_retries_per_event=2):
    """Run calibration with per-event retry for LLM failures."""
    from m11_agent_sim.schemas import (
        CalibrationScore, ValidationCase, CalibrationRun, Direction,
    )

    network = calibrator.network
    BULLISH_THRESHOLD = 0.03
    BEARISH_THRESHOLD = -0.03

    details = []
    direction_hits = 0
    prob_errors = []
    extreme_events = [e for e in events if e.actual_is_extreme]
    extreme_hits = 0
    validation_cases = []

    for i, event in enumerate(events):
        hit = False
        dist = None
        for attempt in range(max_retries_per_event + 1):
            try:
                dist = network.run(event.market_input)
                break
            except Exception as e:
                logger.warning(
                    f"Event {i+1}/{len(events)} {event.event_id} attempt {attempt+1} failed: {e}"
                )
                if attempt < max_retries_per_event:
                    time.sleep(3 * (attempt + 1))
                else:
                    logger.error(f"Event {event.event_id} failed after all retries, using neutral")

        if dist is None:
            from m11_agent_sim.schemas import SentimentDistribution
            dist = SentimentDistribution(
                direction="NEUTRAL",
                bullish_prob=0.333, bearish_prob=0.333, neutral_prob=0.334,
                confidence=0.1, intensity=1.0,
            )

        hit = dist.direction == event.actual_direction
        if hit:
            direction_hits += 1

        actual_bull = 1.0 if event.actual_direction == "BULLISH" else 0.0
        prob_error = abs(dist.bullish_prob - actual_bull)
        prob_errors.append(prob_error)

        if event.actual_is_extreme:
            if dist.intensity >= 7.0:
                extreme_hits += 1

        validation_cases.append(ValidationCase(
            event_id=event.event_id,
            date=event.date,
            description=event.description[:50],
            actual_direction=event.actual_direction,
            simulated_direction=dist.direction,
            direction_match=hit,
            actual_5d_return=event.actual_5d_return,
            simulated_bullish_prob=dist.bullish_prob,
            prob_error=prob_error,
            simulated_intensity=dist.intensity,
            simulated_confidence=dist.confidence,
        ))

        status = "OK" if hit else "MISS"
        logger.info(
            f"[{i+1}/{len(events)}] {event.date} {event.description[:35]} | "
            f"actual:{event.actual_direction} sim:{dist.direction} {status} | "
            f"bull_prob:{dist.bullish_prob:.0%} conf:{dist.confidence:.0%}"
        )

        if (i + 1) % 5 == 0 and i + 1 < len(events):
            time.sleep(1)

    n = len(events)
    direction_accuracy = direction_hits / n
    avg_prob_err = sum(prob_errors) / len(prob_errors) if prob_errors else 0.5
    extreme_recall = extreme_hits / len(extreme_events) if extreme_events else 1.0

    dir_score = direction_accuracy * 100
    prob_score = max(0, (1 - avg_prob_err / 0.5) * 100)
    ext_score = extreme_recall * 100

    weights = {"direction_accuracy": 0.50, "prob_calibration": 0.30, "extreme_recall": 0.20}
    composite = (
        dir_score * weights["direction_accuracy"]
        + prob_score * weights["prob_calibration"]
        + ext_score * weights["extreme_recall"]
    )
    pass_threshold = direction_accuracy >= 0.70 and composite >= 55.0

    score = CalibrationScore(
        total_events=n,
        direction_hits=direction_hits,
        direction_accuracy=round(direction_accuracy, 4),
        prob_calibration_err=round(avg_prob_err, 4),
        extreme_recall=round(extreme_recall, 4),
        composite_score=round(composite, 2),
        pass_threshold=pass_threshold,
        details=[c.model_dump() for c in validation_cases],
    )

    try:
        import uuid as _uuid
        run = CalibrationRun(
            run_id=f"llm_{_uuid.uuid4().hex[:8]}",
            run_timestamp=datetime.now(),
            market="A_SHARE",
            topology="sequential_llm",
            n_events=n,
            score=score,
            cases=validation_cases,
        )
        from m11_agent_sim.calibration_store import CalibrationStore
        store = CalibrationStore()
        store.save_run(run)
    except Exception as e:
        logger.warning(f"Failed to persist LLM calibration run: {e}")

    return score


def _print_comparison(rule_score, llm_score):
    print("\n" + "=" * 70)
    print("M11 CALIBRATION COMPARISON: Rule-based vs LLM")
    print("=" * 70)
    print(f"{'Metric':<25} {'Rule-based':>12} {'LLM':>12} {'Delta':>12}")
    print("-" * 70)

    if rule_score:
        print(f"{'Direction Accuracy':<25} {rule_score.direction_accuracy:>11.2%} {'':>12} {'':>12}")
        print(f"{'Prob Calib Error':<25} {rule_score.prob_calibration_err:>12.3f} {'':>12} {'':>12}")
        print(f"{'Extreme Recall':<25} {rule_score.extreme_recall:>11.2%} {'':>12} {'':>12}")
        print(f"{'Composite Score':<25} {rule_score.composite_score:>12.1f} {'':>12} {'':>12}")
        print(f"{'Pass Threshold':<25} {str(rule_score.pass_threshold):>12} {'':>12} {'':>12}")
        print(f"{'Total Events':<25} {rule_score.total_events:>12d} {'':>12} {'':>12}")

    if llm_score:
        if rule_score:
            print()
        delta_acc = llm_score.direction_accuracy - (rule_score.direction_accuracy if rule_score else 0)
        delta_prob = llm_score.prob_calibration_err - (rule_score.prob_calibration_err if rule_score else 0)
        delta_ext = llm_score.extreme_recall - (rule_score.extreme_recall if rule_score else 0)
        delta_comp = llm_score.composite_score - (rule_score.composite_score if rule_score else 0)

        print(f"{'Direction Accuracy':<25} {rule_score.direction_accuracy if rule_score else 0:>11.2%} {llm_score.direction_accuracy:>11.2%} {delta_acc:>+11.2%}")
        print(f"{'Prob Calib Error':<25} {rule_score.prob_calibration_err if rule_score else 0:>12.3f} {llm_score.prob_calibration_err:>12.3f} {delta_prob:>+12.3f}")
        print(f"{'Extreme Recall':<25} {rule_score.extreme_recall if rule_score else 0:>11.2%} {llm_score.extreme_recall:>11.2%} {delta_ext:>+11.2%}")
        print(f"{'Composite Score':<25} {rule_score.composite_score if rule_score else 0:>12.1f} {llm_score.composite_score:>12.1f} {delta_comp:>+12.1f}")
        print(f"{'Pass Threshold':<25} {str(rule_score.pass_threshold if rule_score else ''):>12} {str(llm_score.pass_threshold):>12}")
        print(f"{'Total Events':<25} {rule_score.total_events if rule_score else 0:>12d} {llm_score.total_events:>12d}")

    print("=" * 70)
    if llm_score:
        if llm_score.pass_threshold:
            print("RESULT: LLM mode PASSES the 70% direction accuracy threshold!")
            print("M11 may be re-evaluated for main chain admission.")
        elif llm_score.direction_accuracy >= 0.65:
            print("RESULT: LLM mode shows SIGNIFICANT improvement but still below 70%.")
            print("Consider: more events, prompt tuning, or adjusted threshold.")
        else:
            print("RESULT: LLM mode still below target. Further investigation needed.")
    print()


def _build_report(rule_score, llm_score, events, provider, elapsed):
    report = {
        "report_type": "m11_llm_calibration",
        "timestamp": datetime.now().isoformat(),
        "provider": provider,
        "n_events": len(events),
        "elapsed_seconds": round(elapsed, 1),
        "rule_based": {
            "direction_accuracy": rule_score.direction_accuracy,
            "prob_calibration_err": rule_score.prob_calibration_err,
            "extreme_recall": rule_score.extreme_recall,
            "composite_score": rule_score.composite_score,
            "pass_threshold": rule_score.pass_threshold,
        },
    }
    if llm_score:
        report["llm"] = {
            "direction_accuracy": llm_score.direction_accuracy,
            "prob_calibration_err": llm_score.prob_calibration_err,
            "extreme_recall": llm_score.extreme_recall,
            "composite_score": llm_score.composite_score,
            "pass_threshold": llm_score.pass_threshold,
        }
        report["delta"] = {
            "direction_accuracy": round(llm_score.direction_accuracy - rule_score.direction_accuracy, 4),
            "composite_score": round(llm_score.composite_score - rule_score.composite_score, 2),
        }
        report["admission_recommendation"] = (
            "PASS" if llm_score.pass_threshold
            else "IMPROVING" if llm_score.direction_accuracy >= 0.65
            else "INSUFFICIENT"
        )
    else:
        report["llm"] = None
        report["admission_recommendation"] = "NO_LLM_DATA"

    direction_dist = {"BULLISH": 0, "BEARISH": 0, "NEUTRAL": 0}
    for e in events:
        direction_dist[e.actual_direction] = direction_dist.get(e.actual_direction, 0) + 1
    report["events_distribution"] = direction_dist

    return report


def _save_report(report):
    reports_dir = ROOT / "docs"
    reports_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = reports_dir / f"m11_llm_calibration_{ts}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    logger.info(f"Report saved to {path}")

    markdown_path = reports_dir / f"m11_llm_calibration_{ts}.md"
    with open(markdown_path, "w", encoding="utf-8") as f:
        f.write(_report_to_markdown(report))
    logger.info(f"Markdown report saved to {markdown_path}")


def _report_to_markdown(report):
    lines = [
        f"# M11 LLM Calibration Report",
        f"",
        f"- **Date**: {report['timestamp']}",
        f"- **Provider**: {report['provider']}",
        f"- **Events**: {report['n_events']}",
        f"- **Duration**: {report['elapsed_seconds']}s",
        f"",
        f"## Rule-based Mode",
        f"",
    ]
    rb = report.get("rule_based", {})
    if rb:
        lines += [
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Direction Accuracy | {rb.get('direction_accuracy', 0):.2%} |",
            f"| Prob Calibration Error | {rb.get('prob_calibration_err', 0):.3f} |",
            f"| Extreme Recall | {rb.get('extreme_recall', 0):.2%} |",
            f"| Composite Score | {rb.get('composite_score', 0):.1f} |",
            f"| Pass Threshold | {rb.get('pass_threshold', False)} |",
        ]

    llm = report.get("llm")
    if llm:
        delta = report.get("delta", {})
        lines += [
            f"",
            f"## LLM Mode",
            f"",
            f"| Metric | Rule-based | LLM | Delta |",
            f"|--------|-----------|-----|-------|",
            f"| Direction Accuracy | {rb.get('direction_accuracy', 0):.2%} | {llm.get('direction_accuracy', 0):.2%} | {delta.get('direction_accuracy', 0):+.2%} |",
            f"| Prob Calibration Error | {rb.get('prob_calibration_err', 0):.3f} | {llm.get('prob_calibration_err', 0):.3f} | |",
            f"| Extreme Recall | {rb.get('extreme_recall', 0):.2%} | {llm.get('extreme_recall', 0):.2%} | |",
            f"| Composite Score | {rb.get('composite_score', 0):.1f} | {llm.get('composite_score', 0):.1f} | {delta.get('composite_score', 0):+.1f} |",
            f"| Pass Threshold | {rb.get('pass_threshold', False)} | {llm.get('pass_threshold', False)} | |",
        ]

    lines += [
        f"",
        f"## Admission Recommendation",
        f"",
        f"**{report.get('admission_recommendation', 'UNKNOWN')}**",
        f"",
        f"Events distribution: {report.get('events_distribution', {})}",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="M11 LLM Mode Calibration")
    parser.add_argument(
        "--provider", default="deepseek",
        choices=["deepseek", "gongfeng", "openclaw", "auto"],
        help="LLM provider to use (default: deepseek)",
    )
    parser.add_argument(
        "--min-events", type=int, default=50,
        help="Minimum number of events to calibrate (default: 50)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Only run rule-based calibration (no LLM calls)",
    )
    parser.add_argument(
        "--topology", default="sequential",
        choices=["sequential", "graph"],
        help="AgentNetwork topology (default: sequential)",
    )
    args = parser.parse_args()

    logs_dir = ROOT / "logs"
    logs_dir.mkdir(exist_ok=True)

    logger.info(f"Starting M11 LLM calibration: provider={args.provider} min_events={args.min_events}")
    run_calibration(
        provider=args.provider,
        min_events=args.min_events,
        dry_run=args.dry_run,
        topology=args.topology,
    )


if __name__ == "__main__":
    main()
