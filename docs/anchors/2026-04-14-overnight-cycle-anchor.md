# 2026-04-14 Overnight Cycle Anchor

## Priority followed
Per overnight instruction, this cycle prioritized LLM runtime repair/validation before any further product feature work.

## Milestone 1 — Verify test runner first
Command run:
- `python -m pytest tests -q`

Result:
- test runner itself works
- suite completed quickly and reported **19 failed, 32 passed**
- failures are mainly legacy schema / enum / test-drift issues, not the primary LLM routing bug for this cycle

Representative failure buckets:
1. `SignalLogicFrame.change_direction` test fixtures still use values like `decrease` / `increase`, but schema now expects enum values like `BULLISH` / `BEARISH` / `NEUTRAL` / `UNCERTAIN`
2. `SourceType` tests still reference removed/renamed members such as `ANNOUNCEMENT` and `REPORT`
3. `OpportunityObject` tests omit required `opportunity_score`
4. `PositionSizing` / `ActionType` tests are behind current schema
5. `test_ingest.py` contains at least one obviously invalid assumption (`len(text) > MAX_CHUNK_CHARS` fails because the fixture text is only 629 chars)

Conclusion:
- `pytest` path is valid
- current red tests are mostly repo drift, not proof of Claude misrouting

## Milestone 2 — Inspect actual provider/model resolution
Inspected:
- `core/llm_client.py`
- `config/llm_config.yaml`
- `test_pipeline.py`
- provider forcing scripts and adapters

Observed active runtime resolution:
- `default_provider: gongfeng`
- `providers.gongfeng.model: gongfeng/gpt-5-4`
- auth type: `gongfeng_oauth`
- module overrides for `m1_decoder`, `m3_judgment`, `m4_action`, `m6_retrospective` do not redirect to Claude

Direct inspection command confirmed:
- default / m1_decoder / m3_judgment all resolve to `gongfeng / gongfeng-gpt-5-4` path semantically (`gongfeng/gpt-5-4`)
- local OAuth credential is present and readable

Repo drift still present:
- several ad-hoc scripts still hardcode `deepseek` / `xfyun`
- docs and anchor history contain old Claude / DeepSeek guidance
- `integrations/llm_adapter.py` and `integrations/gongfeng_llm_client.py` also contain in-progress runtime-related edits in working tree

## Milestone 3 — Validate non-Claude live path
Commands run:
- `python -c "from core.llm_client import LLMClient; ... c.chat_completion(...)"`
- `python test_pipeline.py`

What was confirmed:
1. requests are routed to the intended gongfeng gateway path
2. model resolution stays on `gongfeng/gpt-5-4`
3. this is no longer a Claude-default runtime chain

Live blocker:
- repeated upstream `429 Too Many Requests`
- no usable `Retry-After` value returned
- built-in retry/backoff exhausted after 4 attempts

Observed end-to-end behavior from `python test_pipeline.py`:
- prints `Provider: gongfeng / gongfeng/gpt-5-4`
- fails in M1 with `[GongfengOAuth] RATE_LIMIT_429`
- therefore M1→M3→M4 semantic validation cannot complete in this window

Conclusion:
- routing/auth/config are aligned to a valid non-Claude path
- live runtime validation is currently blocked by upstream rate limiting, not by unresolved provider misconfiguration

## Blocker for this cycle
Primary blocker:
- gongfeng gateway 429 on the required `gongfeng/gpt-5-4` live path

Secondary but separate blocker:
- test suite has substantial schema/test drift that should be repaired in a dedicated cleanup pass after live runtime becomes stable

## Why feature work did not continue
The overnight instruction explicitly said to repair and validate the runtime chain before resuming roadmap work.
Because live validation is still blocked externally by 429s, it would be unsafe to pile on more product features this cycle.

## Recommended next resume point
1. Re-run:
   - `python -m pytest tests -q`
   - `python test_pipeline.py`
2. If gongfeng quota/window clears and a live completion succeeds, then fix the schema/test drift in a focused batch
3. Only after one successful non-Claude end-to-end validation should roadmap feature work resume

## Milestone 4 — Minimal routing cleanup completed

This cycle also applied a narrow code/doc cleanup so adapter-level callers do not accidentally prefer legacy non-primary routes:

Updated:
- `integrations/llm_adapter.py`
  - added explicit `gongfeng` provider option
  - changed `auto` priority to `gongfeng -> openclaw -> deepseek -> rules`
  - ensured DeepSeek path imports `core.llm_client.LLMClient` (not stale module paths)
- `docs/LLM_Config.md`
  - clarified that current primary path is `core.LLMClient` + `gongfeng/gpt-5-4`
  - documented runtime inspection and adapter priority

Validation after cleanup:
- `python .\scripts\inspect_llm_runtime.py` ✅
- `python -c "from integrations.llm_adapter import make_llm_client; ..."` → `LLMAdapter(provider=gongfeng)` ✅
- `python -m pytest tests -q` → still **19 failed, 32 passed** (same schema/test drift bucket, separate from runtime routing)
- `python test_pipeline.py` → still blocked by upstream gongfeng `429` during live M1 call

Net effect:
- repo default and adapter default now both point at a non-Claude gongfeng path more explicitly
- remaining blocker is live rate limiting, not provider selection drift

## Current stop decision
Stop here for this cycle after documenting the blocker, per instruction.
