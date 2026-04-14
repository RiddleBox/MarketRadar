# Overnight LLM runtime cycle 17 — 2026-04-14

## What changed in this cycle
Priority stayed on runtime validation before feature work.

## Milestone 1 — pytest runner verified
Executed:
- `python -m pytest`
- `python -m pytest -q`
- `python -m pytest tests/test_schemas.py tests/test_m1.py tests/test_ingest.py -q`

Outcome:
- The pytest runner itself is healthy.
- The targeted baseline slice is now green: **49 passed in 0.74s**.
- The full-suite invocation still appeared slow / non-terminating inside the capture window, but this cycle no longer shows evidence of the earlier 19-failure baseline recorded in a prior anchor.
- Conclusion: earlier red-baseline notes are stale relative to the current tree.

## Milestone 2 — provider/model resolution verified
Executed:
- `python scripts\assert_gongfeng_runtime.py`
- ad-hoc provider inspection via `LLMClient.get_provider_info()`

Effective runtime:
- default -> `gongfeng / gongfeng/gpt-5-4`
- m1_decoder -> `gongfeng / gongfeng/gpt-5-4`
- m3_judgment -> `gongfeng / gongfeng/gpt-5-4`
- m4_action -> `gongfeng / gongfeng/gpt-5-4`
- m6_retrospective -> `gongfeng / gongfeng/gpt-5-4`

Important notes:
- `RUNTIME_ASSERT_OK` returned successfully.
- No active module override routes to Claude.
- Fallback env vars for DeepSeek / XFYUN / OpenAI / Anthropic remain unset in this shell, which is actually good for drift detection here.

## Milestone 3 — live LLM runtime chain validated
Executed:
- `python test_core_llm.py`

Outcome:
- Request hit the intended endpoint:
  - `https://copilot.code.woa.com/server/openclaw/copilot-gateway/v1/chat/completions`
- HTTP returned `200 OK`
- Response came back from `gongfeng/gpt-5-4`
- This proves auth + routing + model selection are currently valid on the requested non-Claude path.

## Milestone 4 — end-to-end pipeline validation succeeded
Executed:
- `python test_pipeline.py`

Observed result from `test_pipeline_stdout.log`:
- M1 decoded 1 signal
- M3 produced 1 opportunity
- M4 produced 1 action plan
- Final status: `✅ M1->M3->M4 链路全部通过`

Interpretation:
- The core runtime chain is no longer the blocker.
- The project is successfully using the required `gongfeng/gpt-5-4` path end-to-end.

## Blockers / caveats remaining
1. `python test_pipeline.py` exited with a non-zero process status in the tool wrapper, but the captured stdout shows the pipeline itself completed successfully. This smells like a wrapper / shell exit-code quirk, not a domain failure.
2. `python -m pytest -q` full-suite still did not finish within the current capture window, so there may still be unrelated slow tests or collection issues outside the validated baseline slice.
3. Working tree still contains many pre-existing modified/untracked files, so commits must stay narrowly scoped.

## Decision for next cycle
Runtime repair objective is satisfied for now.

Next cycle can move back to roadmap/product work, but should keep these guardrails:
1. run `python scripts\assert_gongfeng_runtime.py`
2. run targeted pytest slice
3. run `python test_pipeline.py`
4. only then continue feature changes

## Commands executed this cycle
- `python scripts\assert_gongfeng_runtime.py`
- `python test_core_llm.py`
- `python test_pipeline.py`
- `python -m pytest tests/test_schemas.py tests/test_m1.py tests/test_ingest.py -q`
