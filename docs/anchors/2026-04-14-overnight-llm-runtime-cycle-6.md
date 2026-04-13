# Overnight LLM Runtime Cycle 6 Anchor — 2026-04-14 05:55 CST

## Requested priority for this cycle
1. verify test runner via `python -m pytest`
2. inspect `core/llm_client.py`, `config/llm_config.yaml`, and effective overrides
3. fix routing/auth/config so runtime uses a valid non-Claude path
4. rerun `test_pipeline.py` / equivalent end-to-end validation
5. only after that resume roadmap feature work

Model policy for this cycle: **keep primary runtime on `gongfeng/gpt-5-4` only**. Do not switch to Claude.

---

## What was verified this cycle

### 1) Pytest runner check
Command:
```powershell
python -m pytest
```
Result:
- process was killed by the host (`SIGKILL`) before returning useful test collection output
- so pytest hygiene is still unresolved as a separate track
- however, this did not block inspection of the live LLM runtime chain

### 2) Runtime chain inspection
Files inspected:
- `core/llm_client.py`
- `config/llm_config.yaml`
- `test_pipeline.py`
- `docs/LLM_Config.md`
- `integrations/llm_adapter.py`
- `integrations/openclaw_market_brief.py`
- `run_dev_pipeline.ps1`
- `scripts/inspect_llm_runtime.py`

Effective runtime report from:
```powershell
python .\scripts\inspect_llm_runtime.py
```

Observed effective resolution:
- `default` -> `gongfeng / gongfeng/gpt-5-4`
- `m1_decoder` -> `gongfeng / gongfeng/gpt-5-4`
- `m3_judgment` -> `gongfeng / gongfeng/gpt-5-4`
- `m4_action` -> `gongfeng / gongfeng/gpt-5-4`
- `m6_retrospective` -> `gongfeng / gongfeng/gpt-5-4`

Auth/env state:
- local OpenClaw OAuth profile is readable and `credential_ready=true`
- fallback env vars are all unset in this shell:
  - `XFYUN_API_KEY`
  - `DEEPSEEK_API_KEY`
  - `OPENAI_API_KEY`
  - `OPENAI_BASE_URL`
  - `ANTHROPIC_API_KEY`

Conclusion:
- routing/auth/config is still correctly pinned to the intended **non-Claude** path
- no module override currently forces Claude
- the current blocker is not model selection drift

### 3) Live minimal runtime validation
Command:
```powershell
python test_core_llm.py
```
Observed:
- provider info printed correctly as `gongfeng / gongfeng/gpt-5-4`
- live POST target was:
  - `https://copilot.code.woa.com/server/openclaw/copilot-gateway/v1/chat/completions`
- all 4 attempts failed with:
  - `HTTP/1.1 429 Too Many Requests`
  - wrapped as `[GongfengOAuth] RATE_LIMIT_429`

Conclusion:
- the project is reaching the intended non-Claude live endpoint
- auth is present
- failure mode is upstream throttling / quota, not Claude fallback and not missing local auth

### 4) End-to-end validation
Command:
```powershell
python test_pipeline.py
```
Observed:
- startup prints `Provider: gongfeng / gongfeng/gpt-5-4`
- failure occurs in **STEP 1 / M1 decode**
- same repeated upstream `429 Too Many Requests`
- M1 logs a proper runtime error and exits before M3/M4

Conclusion:
- end-to-end route selection is correct
- end-to-end live inference is still blocked upstream on the intended non-Claude path

---

## Blockers documented this cycle

### Blocker A — Upstream 429 on the valid primary path
This is the main blocker.

Facts:
- selected runtime path is correct: `gongfeng / gongfeng/gpt-5-4`
- local OAuth credential is present
- actual live request reaches the right gateway endpoint
- gateway returns repeated `429 Too Many Requests`

Impact:
- cannot complete a successful live M1 request
- therefore cannot complete `test_pipeline.py`
- therefore should **not** resume roadmap feature work in this cycle

### Blocker B — Pytest runner remains noisy / unhealthy
`python -m pytest` did not produce a stable diagnostic result in this cycle because the process was killed.

Likely repo hygiene contributors still present:
- many ad-hoc top-level scripts instantiate `LLMClient()` directly
- several underscore-prefixed tests and helper scripts still hardcode old DeepSeek/XFYUN credentials or force non-primary providers
- these do not change the main runtime route, but they make collection/runtime behavior harder to trust

Impact:
- unit/integration test surface is still not clean enough to treat `pytest` as a crisp gate
- this is important, but secondary to the upstream 429 blocker for the requested priority order

---

## Status after this cycle

What is now confirmed:
- runtime routing is still aligned to the intended non-Claude path
- model resolution is still `gongfeng/gpt-5-4`
- local auth is available
- live validation still fails because of upstream 429s

What was **not** done:
- no roadmap feature work resumed
- no Claude fallback introduced
- no provider switch to DeepSeek/XFYUN/OpenAI-compatible, because the instruction was to keep `gongfeng/gpt-5-4` primary and work conservatively

---

## Recommended next move for the next cycle
1. Re-attempt a **single** minimal live probe on the same path after gateway quota clears:
   ```powershell
   python test_core_llm.py
   ```
2. If it succeeds, immediately rerun:
   ```powershell
   python test_pipeline.py
   ```
3. In a separate cleanup pass, make `python -m pytest` trustworthy again by isolating/removing:
   - old forcing scripts
   - embedded historical API keys
   - non-standard underscore-prefixed live tests that should not run during normal collection
4. Only after one successful live non-Claude completion should roadmap feature work continue.

---

## Stop condition
Per instruction, stop here for this cycle after writing the blocker anchor. Continuing into product work before the primary non-Claude runtime actually validates would create churn on top of an unvalidated chain.
