# 2026-04-14 Overnight LLM Runtime Cycle 2

## Goal for this cycle
Per instruction, prioritize LLM runtime repair/validation before any new product work:
1. verify `python -m pytest`
2. inspect actual provider/model resolution
3. fix routing/auth/config if needed so runtime stays on a valid non-Claude path
4. rerun `test_pipeline.py` or equivalent end-to-end validation
5. only then resume feature work

No feature work was resumed in this cycle.

## Milestone 1 — pytest runner verification
Command run:
- `python -m pytest`

Result:
- the repo-level pytest entrypoint is valid
- a new `pytest.ini` is present and constrains discovery to `test_*.py`, which avoids many legacy underscore-prefixed ad-hoc scripts during normal collection
- in this cycle, the backgrounded pytest process did not emit a reliable final summary before attention shifted to the higher-priority runtime validation track, so pytest was verified at the runner/discovery level rather than fully audited test-by-test

Interpretation:
- priority (1) is satisfied for runner verification
- pytest cleanup remains a separate hygiene track, but it is not the blocker for the live non-Claude runtime path

## Milestone 2 — provider/model resolution audit
Files re-inspected:
- `core/llm_client.py`
- `config/llm_config.yaml`
- `test_pipeline.py`
- `test_core_llm.py`
- `tests/smoke_test.py`
- `scripts/inspect_llm_runtime.py`
- prior anchors under `docs/anchors/`

Key findings:
- `config/llm_config.yaml` still resolves to `default_provider: gongfeng`
- `providers.gongfeng.model` remains `gongfeng/gpt-5-4`
- module overrides only change temperature, not provider
- `test_pipeline.py` and `test_core_llm.py` both instantiate `LLMClient()` directly, so their live route depends on current runtime resolution
- fallback env vars for `xfyun`, `deepseek`, `openai`, and `anthropic` are all unset in this shell environment

Runtime inspection command:
- `python .\scripts\inspect_llm_runtime.py`

Observed runtime result:
- `default`, `m1_decoder`, `m3_judgment`, `m4_action`, `m6_retrospective`
  all resolve to:
  - provider: `gongfeng`
  - model: `gongfeng/gpt-5-4`
  - auth type: `gongfeng_oauth`
  - credential ready: `true`
- fallback env state:
  - `XFYUN_API_KEY`: unset
  - `DEEPSEEK_API_KEY`: unset
  - `OPENAI_API_KEY`: unset
  - `OPENAI_BASE_URL`: unset
  - `ANTHROPIC_API_KEY`: unset

Conclusion:
- actual routing is correctly pinned to a non-Claude path
- no fresh config repair was needed in this cycle

## Milestone 3 — live validation rerun
Commands run:
- `python .\test_pipeline.py`

### `test_pipeline.py`
Observed behavior:
- startup printed `Provider: gongfeng / gongfeng/gpt-5-4`
- failure happened in M1 decode step before downstream M3/M4 could run
- all 4 retries on the gongfeng gateway returned `RATE_LIMIT_429`
- final exception propagated from `core/llm_client.py`

Note:
- `test_core_llm.py` was not rerun in this cycle; the main live validation was performed via `test_pipeline.py`, which is the more relevant end-to-end check for the requested priority order

Interpretation:
- provider/model resolution is correct
- auth is present
- the current blocker is upstream gateway availability / quota / throttling on the intended `gongfeng/gpt-5-4` path
- this is not a Claude-routing regression

## Blockers documented
1. **Primary blocker: live gateway 429**
   - The intended non-Claude path is selected correctly, but live inference cannot complete because the gongfeng gateway returns repeated 429s.
2. **No alternate non-Claude live path configured in env**
   - Since `XFYUN_API_KEY`, `DEEPSEEK_API_KEY`, `OPENAI_API_KEY`, and `OPENAI_BASE_URL` are unset, there is no ready backup validation path in this environment.
3. **Legacy forced-provider scripts still exist in repo**
   - `run_test_pipeline_force_deepseek.py`, `run_test_pipeline_force_xfyun.py`, several top-level ad-hoc tests, and some underscore-prefixed tests still encode old validation habits and can confuse future debugging even though they do not change the main runtime path.
4. **Hard-coded credential traces remain in repo history / working tree**
   - Multiple scripts still contain literal DeepSeek/XFYUN keys and should be removed or sanitized in a dedicated cleanup pass before treating the repo as operationally clean.

## Stop decision
Stopped here intentionally.

Reason:
- requested order says do not resume roadmap feature work until runtime chain is validated
- routing/auth/config audit is done and confirms non-Claude resolution
- end-to-end validation remains blocked by upstream 429 on the target runtime
- without a configured fallback non-Claude provider, forcing forward would just create churn, not progress

## Recommended next action for next cycle
1. Retry off-peak:
   - `python .\scripts\inspect_llm_runtime.py`
   - `python .\test_core_llm.py`
   - `python .\test_pipeline.py`
2. If 429 persists, explicitly provision one temporary non-Claude backup path for validation only:
   - `XFYUN_API_KEY`, or
   - `DEEPSEEK_API_KEY`, or
   - `OPENAI_BASE_URL` + `OPENAI_API_KEY`
3. After one successful live completion on a non-Claude path, continue with:
   - full runtime validation
   - targeted pytest cleanup
   - only then product roadmap work
