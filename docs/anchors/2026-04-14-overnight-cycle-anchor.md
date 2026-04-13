# 2026-04-14 Overnight Cycle Anchor

## Priority followed
Per overnight instruction, this cycle prioritized LLM runtime repair/validation before any further product feature work.

## Milestone 1 — Verify test runner first
Commands run:
- `python -m pytest` → starts correctly but is too broad at repo root because it pulls in ad-hoc scripts and live probes
- `python -m pytest tests -q`

Result from scoped suite:
- test runner itself works
- suite completed and reported **19 failed, 32 passed**
- failures are primarily legacy schema / fixture drift, not evidence of Claude routing

Observed failure buckets:
1. `tests/test_ingest.py`
   - chunking expectations no longer match current implementation / fixture size
2. `tests/test_m1.py`
   - mock expectations and schema fields have drifted from current decoder output
3. `tests/test_schemas.py`
   - enums / required fields changed (`ActionType.OPEN` missing, required schema fields tightened, etc.)

Conclusion:
- priority (1) completed: pytest path is valid
- current red tests are repo drift work, separate from the LLM runtime-chain repair target

## Milestone 2 — Inspect actual provider/model resolution
Files inspected:
- `core/llm_client.py`
- `config/llm_config.yaml`
- `test_pipeline.py`
- adapter / integration references via repo-wide search
- `python scripts\inspect_llm_runtime.py`

Confirmed current runtime resolution:
- `default_provider: gongfeng`
- `providers.gongfeng.model: gongfeng/gpt-5-4`
- auth type: `gongfeng_oauth`
- module routes for `m1_decoder`, `m3_judgment`, `m4_action`, `m6_retrospective` all resolve to the same non-Claude path
- local OAuth credential is present and readable

Representative inspection output:
- provider: `gongfeng`
- model: `gongfeng/gpt-5-4`
- base_url: `https://copilot.code.woa.com/server/openclaw/copilot-gateway/v1`
- `credential_ready: true`

Important note:
- env vars for `DEEPSEEK_API_KEY`, `XFYUN_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` are unset on this machine
- but they are no longer part of the active default runtime chain
- `python scripts\inspect_llm_runtime.py` exited successfully and confirmed all core modules resolve to the same `gongfeng / gongfeng/gpt-5-4` route with `credential_ready: true`

## Milestone 3 — Validate non-Claude live path
Commands run:
- `python test_core_llm.py`
- `python test_pipeline.py`

What was verified:
1. requests route to the intended gongfeng gateway endpoint
2. provider/model stay pinned to `gongfeng / gongfeng/gpt-5-4`
3. this is not falling back to Claude by default

Actual blocker:
- both live probes fail with repeated upstream `429 Too Many Requests`
- server does not provide a usable `Retry-After`
- built-in retry/backoff exhausts after 4 attempts

Representative failures:
- `test_core_llm.py`:
  - provider info prints `gongfeng / gongfeng/gpt-5-4`
  - request reaches gateway
  - final error: `[工蜂AI] 调用失败，已重试 4 次。Last: [GongfengOAuth] RATE_LIMIT_429 retry_after=`
- `test_pipeline.py`:
  - prints `Provider: gongfeng / gongfeng/gpt-5-4`
  - fails in M1 decode on the same `RATE_LIMIT_429`

Conclusion:
- priority (2) and (3) are effectively validated at the routing/auth/config level
- priority (4) cannot complete semantically in this window because the live non-Claude path is externally rate-limited

## Repo status observed this cycle
`git status --short --branch` shows unrelated existing working-tree noise, including:
- modified: `integrations/gongfeng_llm_client.py`
- many generated artifacts under `data/`
- ad-hoc test scripts and helpers not yet committed
- this anchor file itself was already modified before this update

Given the overnight instruction to work conservatively, no broad cleanup or feature work was added on top of that state in this cycle.

## Stop decision for this cycle
Stopped here intentionally.

Reason:
- the requested order was to repair and validate the runtime chain before resuming roadmap work
- runtime routing is now aligned to a valid non-Claude path (`gongfeng/gpt-5-4`)
- end-to-end live validation is currently blocked by upstream gongfeng gateway `429`, not by an unresolved config/auth bug
- pytest additionally shows independent schema/test drift that should be handled in a dedicated follow-up batch, not mixed into this blocked live-validation cycle

## Recommended resume point
1. Re-run:
   - `python scripts\inspect_llm_runtime.py`
   - `python test_core_llm.py`
   - `python test_pipeline.py`
2. If gongfeng rate limiting clears, capture one successful live completion on `gongfeng/gpt-5-4`
3. Then fix the `tests/` drift bucket in a dedicated pass:
   - `tests/test_schemas.py` vs current `core/schemas.py`
   - `tests/test_m1.py` mock expectations vs current decoder output
   - `tests/test_ingest.py` chunking assertions vs current splitter behavior
4. Only after one successful non-Claude end-to-end run should roadmap feature work resume
