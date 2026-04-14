# Overnight LLM Runtime Cycle 19 — pytest runner repaired, non-Claude runtime validated

Date: 2026-04-14

## Goal order for this cycle
1. Verify test runner with `python -m pytest`
2. Inspect `core/llm_client.py` + `config/llm_config.yaml` + overrides
3. Repair runtime/auth/config to stay on a valid non-Claude path
4. Re-run `test_pipeline.py` or equivalent end-to-end validation
5. Only then consider broader feature work

## Milestone 1 — pytest runner failure source identified
Initial `python -m pytest` did **not** fail because of provider routing.
It failed during collection because repo-root script `test_pipeline.py` executes at import time and calls `sys.exit(3)` when the business result is `NO_OPPORTUNITIES`.

Observed failure shape:
- pytest collection imported `D:\AIproject\MarketRadar\test_pipeline.py`
- module-level execution reached `sys.exit(3)`
- pytest aborted with `SystemExit: 3`

Conclusion:
- the pytest runner was not trustworthy yet
- this was a test discovery/config hygiene issue, not a Claude-routing regression

## Milestone 2 — runtime resolution inspected
Confirmed via `python .\scripts\inspect_llm_runtime.py`:
- `default_provider`: `gongfeng`
- `default -> gongfeng / gongfeng/gpt-5-4`
- `m1_decoder -> gongfeng / gongfeng/gpt-5-4`
- `m3_judgment -> gongfeng / gongfeng/gpt-5-4`
- `m4_action -> gongfeng / gongfeng/gpt-5-4`
- `m6_retrospective -> gongfeng / gongfeng/gpt-5-4`
- fallback env vars for `XFYUN / DEEPSEEK / OPENAI / ANTHROPIC` are unset in this shell

Also confirmed in code/config inspection:
- `core/llm_client.py` derives `X-Model-Name` from config rather than hardcoding Claude
- `config/llm_config.yaml` keeps the primary route pinned to `gongfeng/gpt-5-4`
- no active module override forces Claude
- `providers.gongfeng.fallback_providers` is empty, so there is no silent provider drift during this repair cycle

Conclusion:
- current runtime routing/auth/model resolution is valid and non-Claude

## Milestone 3 — live runtime chain validated
Equivalent live validation succeeded with a minimal call:

```bash
python -c "from core.llm_client import LLMClient; c=LLMClient(); print(c.chat_completion([{'role':'user','content':'只回复 OK'}], module_name='m1_decoder', max_tokens=20))"
```

Observed result:
- returned `OK`

This proves:
- local OAuth credential is usable
- auth + routing + model selection are valid on `gongfeng/gpt-5-4`
- the blocker is no longer “maybe still using Claude”

## Milestone 4 — conservative runner repair applied
Changed `pytest.ini`:
- added `testpaths = tests`

Reason:
- keep pytest focused on actual `tests/` suite
- avoid collecting repo-root manual debugging / smoke scripts like `test_pipeline.py` and `test_core_llm.py`
- preserve those files as manual E2E scripts instead of import-safe unit tests

## Current status at stop point
Still running at write time:
- `python -m pytest`
- `python test_pipeline.py`

Based on confirmed evidence so far:
- the requested LLM runtime path is valid and live on `gongfeng/gpt-5-4`
- the highest-confidence repair in this cycle is pytest discovery hygiene
- repo still contains many legacy helper scripts/docs mentioning DeepSeek/XFYUN or historical provider assumptions; those remain cleanup debt but are not the active default path

## What to do next
1. Wait for the post-repair `python -m pytest` result and capture exact failures, if any
2. Wait for `python test_pipeline.py` result and capture whether end-to-end business output is:
   - `FULL_CHAIN_OK`, or
   - `NO_OPPORTUNITIES`, or
   - a true runtime/parser failure
3. If both complete cleanly enough, update docs/README briefly, commit, and push
4. If `test_pipeline.py` exposes a real parser/business blocker, write a focused anchor and stop there for the cycle

## Summary
This cycle successfully validated the LLM runtime chain first:
- non-Claude route confirmed
- live completion confirmed
- pytest runner issue narrowed to bad test collection rather than provider failure

Do **not** switch to Claude. Keep primary runtime pinned to `gongfeng/gpt-5-4`.
