# M11 LLM Calibration Report — Iteration 10

> Date: 2026-04-18
> Provider: DeepSeek (deepseek-chat via core.LLMClient)
> Events: 60 (16 annotated + 44 auto-generated from SEED_510300)

---

## 1. Executive Summary

M11 LLM mode calibration completed using DeepSeek API. LLM mode shows **significant improvement** over rule-based mode, but still **below the 70% admission threshold**.

| Mode | Direction Accuracy | Composite Score | Pass Threshold |
|------|-------------------|-----------------|----------------|
| Rule-based (3% threshold) | 50.00% | 29.5 | No |
| Rule-based (2% threshold) | 21.67% | 11.6 | No |
| LLM DeepSeek (2% threshold) | **36.67%** | **22.4** | No |

**Admission recommendation: IMPROVING — not yet admissible**

---

## 2. Detailed Results (2% threshold, 60 events)

### By-Direction Breakdown

| Direction | Rule-based | LLM | Delta |
|-----------|-----------|-----|-------|
| BULLISH (32 events) | 31% (10/32) | **47%** (15/32) | +16% |
| BEARISH (18 events) | 6% (1/18) | **28%** (5/18) | +22% |
| NEUTRAL (10 events) | 20% (2/10) | 20% (2/10) | 0% |

### Key LLM Wins

1. **ev_20241008** (国庆后高开低走): LLM correctly identified BEARISH after rally, rule-based said BULLISH
2. **ev_20241217-19** (年底回调): LLM correctly identified BEARISH continuation, rule-based said NEUTRAL
3. **ev_20250311** (两会闭幕回调): LLM correctly identified BEARISH

### Key LLM Failures

1. **Post-September rally events**: LLM still tends bullish-biased after the 9/24 policy rally
2. **Policy events with NEUTRAL outcome**: LLM over-interprets policy signals as bullish (ev_20241108, ev_20241209)
3. **Modest BEARISH moves (-2% to -4%)**: LLM produces NEUTRAL instead of BEARISH

---

## 3. 3% Threshold Results (Original)

With 3% threshold (13 BULL, 10 BEAR, 37 NEUTRAL):
- Rule-based: **50%** direction accuracy
- LLM mode on 8 key annotated events: **38%** (3/8)

The 3% threshold produces higher accuracy because NEUTRAL events (37/60) are easier to match when agents also produce NEUTRAL for weak-signal cases.

---

## 4. Root Cause Analysis

### Why accuracy is below 70%

1. **Bullish bias in agent aggregation**: Policy signals dominate (weight 0.25), pushing aggregate toward BULLISH even when profit-taking follows
2. **NEUTRAL classification problem**: Both modes struggle when price moves ±2-3% — agents tend to be opinionated rather than neutral
3. **Missing historical context**: Agents cannot see "this is the 3rd day after a major rally, profit-taking is likely" — the signal context only shows current snapshot
4. **Single-instrument calibration**: Using only 510300.SH limits diversity of market scenarios

### Why LLM is better at BEARISH

LLM agents can reason about **causal context** that rules cannot:
- "After a significant rally, profit-taking is common" → BEARISH
- "Policy announcement was already priced in" → NEUTRAL
- "Tariff news creates sustained selling pressure" → BEARISH

---

## 5. Recommendations

### Short-term (next iteration)

1. **Add historical context to prompts**: Include "this is N days after event X" in MarketInput
2. **Post-rally profit-taking rule**: Add a meta-rule that when 5d_return > 5%, increase bearish probability for next events
3. **Lower agent bullish bias**: Reduce policy agent weight from 0.25 to 0.20, increase fundamental agent from 0.15 to 0.20
4. **Multi-instrument catalog**: Add 588000.SH (Sci-Tech ETF) for more diverse scenarios

### Medium-term

5. **Prompt engineering**: Give LLM agents explicit "profit-taking awareness" instructions
6. **Sentiment history**: Use real M10 historical snapshots instead of price-proxy estimation
7. **Ensemble mode**: Combine rule-based + LLM outputs with weighted voting

---

## 6. Calibration Store History

| Run ID | Mode | Events | Direction Acc | Composite | Pass |
|--------|------|--------|--------------|-----------|------|
| run_efce3d68 | Rule 3% | 60 | 50.0% | 29.5 | No |
| run_e48f70f0 | Rule 2% | 60 | 21.7% | 11.6 | No |
| llm_31dad49c | LLM 2% | 60 | **36.7%** | **22.4** | No |

---

## 7. Conclusion

LLM mode improves direction accuracy by +15pp over rule-based, with strongest gains on BEARISH detection (+22pp). However, at 37% overall accuracy, M11 remains **well below** the 70% admission threshold.

**M11 stays in the verification chain.** The next priority is improving agent prompts and aggregation weights to address the systematic bullish bias.
