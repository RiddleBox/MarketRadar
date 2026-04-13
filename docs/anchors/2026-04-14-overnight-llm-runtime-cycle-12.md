# 2026-04-14 Overnight LLM Runtime Cycle 12

## Objective
Continue the overnight MarketRadar work with the requested priority:
1. verify test runner via `python -m pytest`
2. inspect `core/llm_client.py`, `config/llm_config.yaml`, and any runtime overrides
3. repair/confirm routing so the project stays on a valid non-Claude path
4. rerun `test_pipeline.py` or equivalent end-to-end validation
5. stop if blocked; do not resume product roadmap work before runtime validation is real

No feature work was started in this cycle.

## Milestone 1 — pytest runner verification
Command started:
- `python -m pytest -q`

Status in this cycle:
- the full suite was launched successfully, so the runner itself is working
- the full run had not completed before the live LLM validation work became the dominant blocker
- earlier same-day anchors already showed pytest producing real failure summaries rather than runner/bootstrap failures

Interpretation:
- `python -m pytest` is a valid entrypoint on this machine
- remaining pytest issues are repo/test drift issues, not evidence of Claude routing

## Milestone 2 — runtime chain inspection
Files inspected:
- `core/llm_client.py`
- `config/llm_config.yaml`
- `scripts/inspect_llm_runtime.py`
- `test_pipeline.py`
- `integrations/gongfeng_llm_client.py`
- `README.md`

Confirmed current runtime resolution via `python .\scripts\inspect_llm_runtime.py`:
- `default_provider: gongfeng`
- active model: `gongfeng/gpt-5-4`
- module routes:
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

Key code observations:
- `core/llm_client.py` now resolves the model header from config instead of forcing a Claude label
- `config/llm_config.yaml` pins default provider to `gongfeng` and model to `gongfeng/gpt-5-4`
- `module_overrides` only change temperature; no module override currently forces Claude
- `test_pipeline.py` instantiates `LLMClient()` directly, so its live route matches the active runtime config above
- `integrations/gongfeng_llm_client.py` also targets `gongfeng/gpt-5-4` with `X-Model-Name: GPT-5.4`

Conclusion:
- the active runtime chain is correctly aligned to the requested **non-Claude** path
- there is no fresh evidence of accidental Claude fallback in the current main path

## Milestone 3 — end-to-end validation attempt
Command started:
- `python test_pipeline.py`

Observed output during this cycle:
- startup resolves `Provider: gongfeng / gongfeng/gpt-5-4`
- the request reaches the intended provider
- retries hit repeated upstream failures:
  - attempt 1 → `RATE_LIMIT_429`
  - attempt 2 → `RATE_LIMIT_429`
  - attempt 3 → `RATE_LIMIT_429`
  - attempt 4 was still pending when this anchor was written

Interpretation:
- live validation is reaching the correct provider/model
- the blocker is upstream throttling on the required non-Claude path
- this is **not** a Claude-routing regression
- this is **not** a local auth-profile resolution failure

## Blockers
### Primary blocker
The gongfeng gateway for `gongfeng/gpt-5-4` is still returning repeated `429` during live validation.

### Secondary blocker
No sanctioned non-Claude fallback credentials are configured in environment, so there is no alternate live validation path available in this shell for this cycle.

### Tertiary blocker
The repo still contains many legacy tests/scripts and historical drift; even after rate limits clear, regression cleanup will still be needed to make the suite trustworthy.

## Stop point for this cycle
Stop here for this cycle.

Reason:
- requested priority was followed
- runtime inspection confirms the active path is already `gongfeng/gpt-5-4`
- E2E validation was attempted again and is blocked upstream by `429`
- continuing into roadmap/product work before one successful live non-Claude completion would violate the requested order

## Recommended next actions
1. retry `python test_pipeline.py` in a quieter quota window until one live non-Claude completion succeeds
2. if policy allows, provision exactly one temporary non-Claude backup validation path (`xfyun`, `deepseek`, or OpenAI-compatible) without changing the primary policy away from `gongfeng/gpt-5-4`
3. after live validation succeeds, return to pytest contract cleanup
4. only then resume roadmap feature work
