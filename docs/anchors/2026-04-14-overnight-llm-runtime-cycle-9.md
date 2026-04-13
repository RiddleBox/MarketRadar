# 2026-04-14 Overnight LLM Runtime Cycle 9

## Goal for this cycle
Strictly follow the requested order:
1. verify test runner with `python -m pytest`
2. inspect actual provider/model resolution from `core/llm_client.py`, `config/llm_config.yaml`, and runtime adapters
3. ensure a valid non-Claude route is in effect
4. rerun end-to-end validation only after the route is verified

No new feature work was started in this cycle.

## Milestone 1 — runtime route re-verified
Files re-checked:
- `core/llm_client.py`
- `config/llm_config.yaml`
- `integrations/llm_adapter.py`
- `scripts/inspect_llm_runtime.py`
- `test_pipeline.py`
- `tests/smoke_test.py`

Command run:
- `python .\scripts\inspect_llm_runtime.py`

Observed resolution:
- default provider: `gongfeng`
- module routes (`m1_decoder`, `m3_judgment`, `m4_action`, `m6_retrospective`) all resolve to `gongfeng`
- resolved model everywhere: `gongfeng/gpt-5-4`
- gongfeng OAuth credential is present and locally usable
- fallback env credentials are not configured for:
  - `XFYUN_API_KEY`
  - `DEEPSEEK_API_KEY`
  - `OPENAI_API_KEY`
  - `OPENAI_BASE_URL`
  - `ANTHROPIC_API_KEY`

Conclusion:
- the project is currently routed to a valid **non-Claude** path
- there is no evidence of accidental Claude routing in the active runtime chain

## Milestone 2 — end-to-end validation blocker reproduced on the correct route
Command run:
- `python .\test_pipeline.py`

Observed behavior:
- request goes to `https://copilot.code.woa.com/server/openclaw/copilot-gateway/v1/chat/completions`
- `core.llm_client` logs repeated `RATE_LIMIT_429`
- backoff sequence is active (`8s`, then `16s`, then continued retry path)

Interpretation:
- this is an upstream availability / rate-limit blocker on the intended provider
- this is **not** a Claude fallback issue
- this is **not** a missing-auth issue
- with no non-Claude fallback credentials configured, there is no alternate live route available in this environment for this cycle

## Milestone 3 — pytest verification status
Command started:
- `python -m pytest`

Purpose of this step in this cycle:
- confirm repo-level pytest entrypoint still works
- separate local test drift from LLM runtime routing issues

Current interpretation while the live run is in progress:
- the LLM runtime blocker is already independently reproduced by `test_pipeline.py`
- even if pytest reports additional drift, the priority blocker for this cycle remains the upstream `gongfeng` 429 on the validated non-Claude chain

## Stop point for this cycle
Stop here if `python -m pytest` does not reveal a simpler local misroute.

Reason:
- requested order says to validate runtime first
- runtime route has been validated and remains pinned to `gongfeng/gpt-5-4`
- live end-to-end validation is blocked by upstream 429 on the correct route
- adding product features before one successful live non-Claude completion would violate the requested priority

## Next recommended action
1. complete the current pytest run and capture its summary
2. retry live validation off-peak:
   - `python .\scripts\inspect_llm_runtime.py`
   - `python .\test_pipeline.py`
   - optionally `python tests\smoke_test.py`
3. if 429 persists, provide one acceptable non-Claude fallback credential (`xfyun`, `deepseek`, or openai-compatible) or wait for provider quota/reset
4. only after one successful live non-Claude pass, resume broader roadmap work
