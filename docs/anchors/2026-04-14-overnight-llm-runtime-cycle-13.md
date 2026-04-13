# 2026-04-14 Overnight LLM Runtime Cycle 13

## Objective
Continue the MarketRadar overnight work with strict priority:
1. verify the test runner with `python -m pytest`
2. inspect `core/llm_client.py`, `config/llm_config.yaml`, and runtime overrides
3. repair/confirm routing so the project stays on a valid non-Claude path
4. rerun `test_pipeline.py` or equivalent end-to-end validation
5. stop and write an anchor if blocked

No roadmap/product feature work was started in this cycle.

## Milestone 1 — pytest entrypoint verification
Commands run:
- `python -m pytest`
- `python -m pytest -q tests/test_schemas.py tests/test_m1.py tests/test_ingest.py`

Findings:
- The pytest runner itself is valid on this machine; collection and execution both start normally.
- Focused test run completed with a real summary: `19 failed, 30 passed`.
- Failures are concentrated in existing schema / decoder / ingest contract drift, for example:
  - `tests/test_schemas.py`
  - `tests/test_m1.py`
  - `tests/test_ingest.py`
- This confirms the runner is not the blocker; there is no bootstrap failure at the pytest entrypoint.

Interpretation:
- Priority step (1) is satisfied.
- Current pytest failures are repository correctness issues, not evidence of Claude routing.

## Milestone 2 — runtime chain inspection
Files inspected in this cycle:
- `core/llm_client.py`
- `config/llm_config.yaml`
- `test_pipeline.py`
- `scripts/inspect_llm_runtime.py`
- repository grep for provider/model overrides

Observed effective runtime via `python .\\scripts\\inspect_llm_runtime.py`:
- `default_provider: gongfeng`
- resolved model for default and active modules: `gongfeng/gpt-5-4`
- module routes confirmed:
  - `default -> gongfeng / gongfeng/gpt-5-4`
  - `m1_decoder -> gongfeng / gongfeng/gpt-5-4`
  - `m3_judgment -> gongfeng / gongfeng/gpt-5-4`
  - `m4_action -> gongfeng / gongfeng/gpt-5-4`
  - `m6_retrospective -> gongfeng / gongfeng/gpt-5-4`
- gongfeng OAuth credential readiness: `true`
- fallback env vars remain unset in this shell:
  - `XFYUN_API_KEY`
  - `DEEPSEEK_API_KEY`
  - `OPENAI_API_KEY`
  - `OPENAI_BASE_URL`
  - `ANTHROPIC_API_KEY`

Code-level interpretation:
- `core/llm_client.py` resolves model headers from config and no longer hardcodes a Claude label.
- `config/llm_config.yaml` keeps the primary route on `gongfeng` with model `gongfeng/gpt-5-4`.
- `module_overrides` only adjust temperature and do not force Claude.
- `test_pipeline.py` uses `LLMClient()` directly, so its live route follows the same inspected config.

Conclusion:
- The actual runtime chain remains correctly pinned to the requested non-Claude path.
- There is no fresh sign of accidental Claude fallback in the main path.

## Milestone 3 — live end-to-end validation
Command run:
- `python test_pipeline.py`

Observed output:
- startup printed `Provider: gongfeng / gongfeng/gpt-5-4`
- live request reached the intended provider/model path
- M1 decode failed only after repeated upstream throttling:
  - attempt 1 -> `RATE_LIMIT_429`
  - attempt 2 -> `RATE_LIMIT_429`
  - attempt 3 -> `RATE_LIMIT_429`
  - attempt 4 -> `RATE_LIMIT_429`
- final failure surfaced as:
  - `[工蜂AI] 调用失败，已重试 4 次。Last: [GongfengOAuth] RATE_LIMIT_429 retry_after=`

Interpretation:
- end-to-end validation reached the intended non-Claude runtime
- failure mode is upstream quota / throttling on the gongfeng gateway
- this is not a routing regression
- this is not a local auth-profile failure

## Blockers
### Primary blocker
The valid primary runtime path (`gongfeng / gongfeng/gpt-5-4`) is still being throttled upstream with repeated `429` responses.

### Secondary blocker
No sanctioned non-Claude fallback credentials are configured in environment, so there is no alternate live validation path available in this shell for this cycle.

### Tertiary blocker
Pytest still reports 19 focused failures across legacy tests/contracts; this cleanup should happen only after at least one successful live non-Claude completion validates the runtime chain.

## Stop point for this cycle
Stop here for this cycle.

Reason:
- requested order was followed
- pytest entrypoint was verified
- runtime inspection confirmed the active path is `gongfeng/gpt-5-4`
- live validation was retried and is still blocked by upstream `429`
- continuing into feature work before one successful live non-Claude completion would violate the requested priority

## Recommended next actions
1. Retry `python test_pipeline.py` during a quieter quota window until one live `gongfeng/gpt-5-4` completion succeeds.
2. If policy allows, add exactly one temporary non-Claude backup validation credential (`xfyun`, `deepseek`, or OpenAI-compatible) without changing the primary default away from `gongfeng/gpt-5-4`.
3. After one successful live validation, return to pytest contract cleanup (`tests/test_schemas.py`, `tests/test_m1.py`, `tests/test_ingest.py`).
4. Only then resume roadmap/product work.
