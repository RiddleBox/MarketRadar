# 2026-04-14 LLM Runtime Blocker Anchor

## Context
Overnight repair cycle prioritized LLM runtime validation before any feature work.

## What was verified
1. `python -m pytest` initially failed during collection because many scripts/tests instantiated `LLMClient()` while `config/llm_config.yaml` still pointed `default_provider: openai`.
2. Environment inspection showed `OPENAI_BASE_URL` and `OPENAI_API_KEY` were unset on this machine.
3. Local OpenClaw OAuth credentials were present and valid at:
   - `C:\Users\Administrator\.openclaw\agents\main\agent\auth-profiles.json`
4. Runtime inspection after config repair now resolves to:
   - provider: `gongfeng`
   - model: `gongfeng/gpt-5-4`
   - auth: `gongfeng_oauth`

## Changes made this cycle
- Switched `config/llm_config.yaml` default provider from `openai` to `gongfeng`
- Reordered `gongfeng` fallbacks to prefer non-Claude paths: `xfyun`, `deepseek`, `openai`
- Updated `README.md` to document `gongfeng/gpt-5-4` as the default runtime path
- Updated `docs/LLM_Config.md` to document GPT-5.4 headers/model instead of Claude defaults

## Validation results
### 1) Test runner
- `python -m pytest`
- Result: collection progressed past the old unresolved OpenAI base_url failure, but suite still contains unrelated legacy failures outside this cycle.
- Confirmed prior top-level LLM routing failure was real and fixable.

### 2) End-to-end script
- `python test_pipeline.py`
- Result after config repair: provider resolves correctly to `gongfeng / gongfeng/gpt-5-4`, but live calls hit repeated `429` rate limiting from the gongfeng gateway.

## Current blocker
Primary blocker is gateway/runtime rate limiting on the valid non-Claude path:
- `[GongfengOAuth] RATE_LIMIT_429 retry_after=`
- No usable `Retry-After` returned by server
- Current backoff exhausted after 4 attempts

## What not to assume
- This is **not** the previous misrouting bug anymore.
- This cycle did **not** validate end-to-end semantic correctness because live inference never cleared the provider gateway due to 429.

## Recommended next step
1. Add/test a conservative non-Claude live fallback path for temporary validation (`xfyun` or `deepseek`) only if credentials are intentionally supplied.
2. Or add a test-time forced provider override / mock layer so `pytest` does not depend on live gateway availability during collection.
3. Re-run `test_pipeline.py` once gateway quota clears, keeping model pinned to `gongfeng/gpt-5-4` when using gongfeng.

## Stop condition for this cycle
Stopped here because the requested priority was to repair and validate the LLM runtime chain first, and the remaining blocker is external rate limiting rather than an unresolved routing/config issue.
