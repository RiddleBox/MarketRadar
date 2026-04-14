# Overnight cycle anchor — 2026-04-14

## Priority executed
Per instruction, this cycle prioritized LLM runtime repair/validation ahead of further roadmap features.

Execution order followed:
1. Start with `python -m pytest`
2. Inspect runtime resolution in `core/llm_client.py` + `config/llm_config.yaml` + repo overrides
3. Validate the active provider/model path
4. Attempt live LLM probe before resuming feature work

## Milestone 1 — test runner path verified, but baseline suite is not green
First command started exactly as requested:
- `python -m pytest`

That full run did not finish cleanly within a reasonable capture window, so I narrowed to the existing baseline unit slice:
- `python -m pytest tests/test_schemas.py tests/test_m1.py tests/test_ingest.py -q`

Result:
- **19 failed, 30 passed**

Observed failure groups:
- `tests/test_schemas.py`: multiple Pydantic/schema mismatches
- `tests/test_m1.py`: decoder expectations no longer match current schema/parser behavior
- `tests/test_ingest.py`: chunking behavior differs from test assumptions

Interpretation:
- The pytest runner itself is fine.
- The repo already has a **pre-existing red baseline** unrelated to today’s LLM-route repair.
- It is unsafe to treat current unit-test failures as evidence against the repaired provider chain without first separating baseline regressions from runtime/auth problems.

## Milestone 2 — provider/model resolution inspected
Inspected:
- `core/llm_client.py`
- `config/llm_config.yaml`
- `scripts/inspect_llm_runtime.py`
- `run_dev_pipeline.ps1`
- repo-wide provider references

Current effective runtime resolution is:
- default provider: `gongfeng`
- model: `gongfeng/gpt-5-4`
- module routes:
  - `default` -> `gongfeng / gongfeng/gpt-5-4`
  - `m1_decoder` -> `gongfeng / gongfeng/gpt-5-4`
  - `m3_judgment` -> `gongfeng / gongfeng/gpt-5-4`
  - `m4_action` -> `gongfeng / gongfeng/gpt-5-4`
  - `m6_retrospective` -> `gongfeng / gongfeng/gpt-5-4`

Important findings:
- No module override currently forces Claude.
- `gongfeng_oauth` credentials are available locally.
- Fallback env vars for `xfyun`, `deepseek`, `openai`, `anthropic` are currently unset in this shell.
- There are still many old repo scripts that explicitly force `deepseek` or `xfyun`; they remain a future cleanup target because they can confuse debugging, but they are **not** the active default route now.

## Milestone 3 — live runtime probe attempted
Executed:
- `python test_core_llm.py`

Observed:
- provider info prints as `gongfeng / gongfeng/gpt-5-4`
- request reaches the intended endpoint:
  - `POST https://copilot.code.woa.com/server/openclaw/copilot-gateway/v1/chat/completions`
- auth is present and accepted far enough to hit the model gateway
- response repeatedly returns `429 Too Many Requests`
- built-in retry loop exhausts after 4 attempts

Interpretation:
- This cycle **did validate the routing/auth direction**.
- The project is **not accidentally falling back to Claude**.
- The current blocker is upstream rate limiting on the gongfeng gateway, not provider resolution.

## Blockers for this cycle
1. **Live validation blocker**: repeated `429` from the gongfeng gateway prevents proving a successful real completion.
2. **Baseline test blocker**: repo unit tests are already red in schema/M1/ingest areas, so a fully green pytest milestone is not yet a reliable acceptance gate for the LLM repair alone.
3. **Working tree noise**: there are many unrelated modified/untracked files in the repo, so making a clean commit from this cycle without first isolating intent would be risky.

## Decision for this cycle
Stop here conservatively.

Why:
- The runtime chain has been inspected and resolves to the requested non-Claude model path.
- A real live probe was attempted and reached the correct gateway.
- Upstream `429` prevents end-to-end success validation.
- Existing red tests indicate broader baseline drift, so continuing into feature work would stack new changes on top of an unvalidated runtime and a non-green baseline.

## Recommended next resume order
1. Re-run `python .\scripts\inspect_llm_runtime.py`
2. Retry `python test_core_llm.py` during a quieter window until at least one successful non-Claude completion returns
3. After that, run `python test_pipeline.py`
4. Separately triage the baseline failures in:
   - `tests/test_schemas.py`
   - `tests/test_m1.py`
   - `tests/test_ingest.py`
5. Only after one successful live completion plus a deliberate test-baseline triage should roadmap feature work resume

## Commands executed this cycle
- `python -m pytest`
- `python -m pytest -q`
- `python .\scripts\inspect_llm_runtime.py`
- `python test_core_llm.py`
- `python -m pytest tests/test_schemas.py tests/test_m1.py tests/test_ingest.py -q`
