# M11 Agent Simulation — First Principles

## Role Definition

M11 is a **verification tool**, not a production judgment module. It simulates market participant behavior through multi-agent role-play to produce sentiment probability distributions, which can be compared against actual outcomes for calibration purposes.

## Core Principles

### P1: Simulation is not judgment
M11 simulates how different market participants *might* react. It does not make production trading decisions. Its output (SentimentDistribution) is a probability distribution, not a directional recommendation.

### P2: Probability distribution over point prediction
M11 outputs bullish/bearish/neutral probabilities with confidence intervals, never a single direction prediction. The goal is:
```
P(ΔPrice | S_simulated) ≈ P(ΔPrice | S_historical_actual)
```

### P3: Calibration evidence drives admission
M11 may only be considered for main chain integration when:
- Direction accuracy ≥ 70% on ≥ 50 historical events
- Composite score ≥ 55 (weighted: direction 50%, prob calibration 30%, extreme recall 20%)
- Calibration is reproducible across multiple runs

**Current status**: Direction accuracy 50% (rule-based) / 37% (LLM, 2% threshold) — BELOW threshold. M11 remains in the verification chain, NOT the main production chain.

### P4: Agent roles model market microstructure
Each agent represents a real market participant archetype:
- PolicySensitiveAgent: A-share policy-driven behavior (weight 0.25)
- NorthboundFollowerAgent: Foreign capital flow follower (weight 0.25)
- TechnicalAgent: Price/volume pattern trader (weight 0.15)
- SentimentRetailAgent: Retail sentiment follower (weight 0.20)
- FundamentalAgent: Value/valuation investor (weight 0.15)

### P5: Dual mode operation
- **Rule-based mode**: Deterministic, offline-capable, testable. Used for unit tests and regression.
- **LLM mode**: Uses external LLM for richer reasoning. Requires API access and costs tokens. Gracefully degrades to rule-based on failure.

### P6: Historical events are ground truth
`actual_direction` is computed from real 5-day price returns post-event, not from subjective labels. The 3% threshold for BULLISH/BEARISH distinguishes meaningful moves from noise.

## Prohibited Behaviors

- M11 must NOT directly trigger trading actions
- M11 must NOT bypass M3 (the only judgment module) to influence M4
- M11 must NOT be used as a real-time production signal source
- Agent weights must NOT be hand-tuned to match specific historical outcomes (overfitting)
- M11 must NOT modify signals in M2 or any upstream module

## Calibration Protocol

1. Load ≥ 50 historical events from event_catalog
2. Run each event through AgentNetwork
3. Compare simulated direction vs actual direction (from price data)
4. Compute: direction_accuracy, prob_calibration_error, extreme_recall, composite_score
5. Persist results to CalibrationStore for trend analysis
6. Compare rule-based vs LLM modes to quantify LLM value-add

## Known Limitations

- **NEUTRAL classification**: Both modes struggle when actual direction is NEUTRAL (small moves within ±3%)
- **Bullish bias**: Policy signals systematically push agents toward BULLISH, even when outcomes are BEARISH (e.g., post-rally profit-taking)
- **Sentiment estimation**: Historical sentiment context uses price-proxy estimation, not real M10 data
- **Single instrument**: Current calibration uses only 510300.SH (CSI 300 ETF)
- **LLM cost**: Full 60-event LLM calibration requires ~300 API calls (~20 min with DeepSeek)
