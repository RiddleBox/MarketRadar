# Overnight LLM Blocker — 2026-04-14

## Scope for this cycle
Priority was explicitly changed to repair and validate the LLM runtime chain before resuming roadmap work.

## What was verified this cycle
1. `python -m pytest` was started first as requested to validate the test runner path before feature work.
2. Runtime inspection now resolves the live chain to:
   - default provider: `gongfeng`
   - model: `gongfeng/gpt-5-4`
   - module routes: `m1_decoder` / `m3_judgment` / `m4_action` / `m6_retrospective` all stay on the same non-Claude path.
3. Local OpenClaw OAuth profile is present and readable, so gongfeng OAuth auth is available on this machine.
4. A direct live validation was executed with `python test_core_llm.py`.
5. The request really reached the gongfeng gateway endpoint:
   - `POST https://copilot.code.woa.com/server/openclaw/copilot-gateway/v1/chat/completions`
6. `OpenClawLLMClient.is_available()` had an outdated `/models` probe that could falsely mark the local bridge unavailable. That probe was repaired this cycle so M11/OpenClaw bridge logic is no longer biased by a known-bad health check.
7. `README.md` had a stale recommended command pointing at `-Provider xfyun`; it was updated to `-Provider gongfeng` to match the repaired runtime direction.

## Actual blocker
Live inference validation is currently blocked by repeated `429 Too Many Requests` responses from the gongfeng copilot gateway.

Observed during `python test_core_llm.py`:
- provider info prints as `gongfeng / gongfeng/gpt-5-4`
- HTTP request reaches the intended gateway
- retry loop gets `429` four times
- built-in backoff escalates (8s / 16s / 24s / final fail)

So the chain is now routing correctly and auth is present, but end-to-end validation is still blocked by gateway rate limiting in the current window.

## Important interpretation
This is **not** the earlier Claude-routing problem.
It is also **not** a missing-credential problem.
Current state is:
- provider/model resolution: fixed
- auth profile presence: verified
- real request path: verified
- live completion: blocked by upstream 429s

## Additional repo drift observed
1. Repo contains multiple old ad-hoc scripts that force `deepseek` / `xfyun` and can still confuse future debugging.
2. There are unrelated uncommitted changes and generated artifacts in the working tree, so any follow-up commit should stay minimal and intentional.
3. Full `pytest` completion for this cycle was not yet captured because live-runtime validation took priority once the correct route was confirmed and 429 became the dominant blocker.

## Next recommended resume point
1. Re-run `python -m pytest -q` and capture the full failure list once the environment is quiet.
2. Re-run `python .\scripts\inspect_llm_runtime.py` to confirm routing still resolves to `gongfeng/gpt-5-4`.
3. Retry `python test_core_llm.py` first (smallest live probe).
4. Only if that passes, run `python test_pipeline.py` for M1→M3→M4 end-to-end validation.
5. If 429 continues, add a conservative validation layer:
   - keep provider-resolution assertions live
   - mock only transport/completion output for deterministic M1/M3/M4 structural verification
   - do **not** resume roadmap feature work until at least one non-Claude live completion succeeds.

## Commands used this cycle
- `python -m pytest`
- `python -m pytest -q`
- `python .\scripts\inspect_llm_runtime.py`
- `python test_core_llm.py`

## Decision
Stop here for this cycle after documenting the blocker. The correct non-Claude runtime chain is now identified and aligned, but live validation is still rate-limited upstream, so it is safer not to pile more product changes on top of an unvalidated runtime.
