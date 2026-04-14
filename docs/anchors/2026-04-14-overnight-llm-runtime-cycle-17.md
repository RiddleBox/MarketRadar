# Overnight LLM runtime cycle 17 — 2026-04-14

## Objective for this cycle
Continue the MarketRadar overnight work with the same hard priority:
1. verify test runner via `python -m pytest`
2. inspect `core/llm_client.py` + `config/llm_config.yaml` + effective overrides
3. repair/validate routing so the project stays on a valid non-Claude path
4. rerun end-to-end validation before any new feature work

Model policy preserved:
- target model remains `gongfeng/gpt-5-4`
- no switch to Claude
- no feature work resumed in this cycle

## Milestone 1 — pytest runner verified and focused baseline repaired
Executed:
- `python -m pytest`
- `python -m pytest tests/test_schemas.py tests/test_m1.py tests/test_ingest.py -q`

What changed this cycle:
- updated `tests/test_schemas.py` fixtures to match current schema contracts
- updated `tests/test_m1.py` mock payload/enums to match current source types and logic-frame enums
- updated `tests/test_ingest.py` oversized paragraph fixture so it actually exceeds chunk threshold
- adjusted `pipeline/ingest.py` to preserve short-but-valid tail chunks instead of dropping them

Result:
- focused regression slice is now green
- `49 passed`

Interpretation:
- step (1) is fully satisfied
- pytest runner is healthy
- the earlier failures were mostly schema/test drift, not proof of a broken LLM runtime chain

## Milestone 2 — effective provider/model path revalidated
Executed:
- `python scripts\inspect_llm_runtime.py`
- manual inspection of `core/llm_client.py` and `config/llm_config.yaml`

Confirmed:
- default provider: `gongfeng`
- active model: `gongfeng/gpt-5-4`
- module overrides for `m1_decoder`, `m3_judgment`, `m4_action`, `m6_retrospective` all remain on `gongfeng/gpt-5-4`
- non-gongfeng fallback env vars are unset in this shell
- no Claude path is active in this runtime

Interpretation:
- step (2) and the routing part of step (3) remain satisfied
- this cycle did not observe silent fallback to Claude

## Milestone 3 — M3 JSON robustness improved
Problem observed:
- `test_pipeline.py` still occasionally reached M3 Step B and then failed on malformed/truncated JSON from the live model response
- earlier behavior made this look too similar to a genuine "no opportunity" result

Repairs applied:
- hardened `m3_judgment/judgment_engine.py` JSON extraction logic
- added a targeted one-shot repair retry when Step B returns invalid JSON
- added automatic debug-anchor emission under `docs/anchors/` for parse/build failures

Why this matters:
- we can now distinguish between:
  - legitimate `is_opportunity=false`
  - malformed model JSON
  - object-build/schema failures after a positive opportunity judgment

## Milestone 4 — end-to-end validation rerun
Executed:
- `python test_pipeline.py`

Observed state after this cycle:
- provider still resolves to `gongfeng / gongfeng/gpt-5-4`
- M1 can execute on the intended non-Claude path
- M3 Step B is more diagnosable now, but live end-to-end validation is still not consistently green because the model output can still be malformed/truncated in some runs
- failure anchors are now automatically written for inspection instead of silently disappearing into logs

Interpretation:
- the runtime chain is much better instrumented and still pinned to the intended model
- the remaining blocker is no longer confusion about routing/auth/provider selection
- the remaining blocker is live-response reliability / structured JSON compliance at M3 Step B

## Blockers at stop point
1. **Primary blocker: M3 live JSON reliability**
   - provider/model routing is correct
   - Step B live output can still be malformed/truncated on some runs
   - end-to-end validation is therefore not yet stable enough to declare fully repaired
2. **Secondary blocker: dirty working tree**
   - repo already contains many unrelated modified/untracked files from earlier overnight work
   - commit isolation must be done carefully to avoid bundling unrelated artifacts

## Decision for this cycle
Stop here conservatively.

Reason:
- priority order was followed
- test runner was verified and improved
- runtime resolution was rechecked and remains fixed on `gongfeng/gpt-5-4`
- end-to-end validation was retried after parser hardening
- feature work should still remain paused until one clean M1→M3→M4 live pass is achieved

## Recommended next resume order
1. inspect the newest `docs/anchors/m3-stepb-parse-failure-*.md`
2. tighten Step B prompt/output contract or add an explicit JSON-schema response format strategy
3. rerun `python test_pipeline.py`
4. only after a clean live pass, resume roadmap work

## Files changed this cycle
- `tests/test_schemas.py`
- `tests/test_m1.py`
- `tests/test_ingest.py`
- `pipeline/ingest.py`
- `m3_judgment/judgment_engine.py`

## Commands executed this cycle
- `python -m pytest`
- `python -m pytest tests/test_schemas.py tests/test_m1.py tests/test_ingest.py -q`
- `python scripts\inspect_llm_runtime.py`
- `python test_pipeline.py`
