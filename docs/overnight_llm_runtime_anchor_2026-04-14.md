# Overnight LLM Runtime Anchor — 2026-04-14

## Goal of this cycle
Repair and validate the LLM runtime chain before adding more product features.
Model policy for this cycle: **gongfeng/gpt-5-4 only as the primary path**; do not restore Claude as a default path.

## What was verified from source inspection

### 1) Current unified runtime client
- File: `core/llm_client.py`
- The real runtime entry used by M1/M3/M4 is `LLMClient`.
- `gongfeng` provider is implemented as a custom OAuth client (`GongfengOAuthClient`).
- Default model fallback inside code is already `gongfeng/gpt-5-4`.
- For `gongfeng`, `auth_type: gongfeng_oauth` reads local OpenClaw auth profile.
- Automatic fallback list exists, but only triggers under limited conditions (mainly gongfeng rate limit).

### 2) Current config resolution
- File: `config/llm_config.yaml`
- `default_provider: gongfeng`
- `providers.gongfeng.model: gongfeng/gpt-5-4`
- `module_overrides` currently only change temperature, not provider.
- No module override currently forces Claude.

### 3) Entry-point mismatch / operator confusion risk
- File: `run_dev_pipeline.ps1`
- Script default parameter is still:
  - `[string]$Provider = "deepseek"`
- This conflicts with the repo’s documented/default runtime direction (`gongfeng`).
- Result: even if core config is correct, operators may still launch the wrong route by habit.

### 4) Test entrypoint inconsistency
- `README.md` references `test_pipeline.py` as the end-to-end validation entry.
- `tests/test_pipeline.py` does not exist.
- Actual file found: project root `test_pipeline.py`
- `tests/smoke_test.py` also exists and performs broader real-LLM smoke validation.

## Blockers in this cycle

### Blocker A — shell execution unavailable in current cron run
Attempted shell actions were blocked by tool/runtime restrictions in this session:
- `python -m pytest`
- `git status`
- ripgrep search

So this cycle could not complete the required live sequence:
1. run pytest
2. run runtime inspection script
3. run `test_pipeline.py` / smoke validation
4. commit
5. push

### Blocker B — runtime not yet proven live
By code inspection only, the config chain looks correct for gongfeng.
But without executing:
- `python -m pytest`
- `python .\scripts\inspect_llm_runtime.py`
- `python test_pipeline.py`

we still do **not** have proof that:
- OAuth token is present and valid
- runtime resolves to gongfeng at execution time
- M1/M3/M4 chain works end-to-end
- fallback behavior won’t unexpectedly route to a non-target provider in practice

## Minimum next actions when shell execution is available
1. Run `python -m pytest`
2. Run `python .\scripts\inspect_llm_runtime.py`
3. Fix `run_dev_pipeline.ps1` default provider from `deepseek` to `gongfeng`
4. Re-run `python test_pipeline.py`
5. Optionally run `python tests/smoke_test.py`
6. Update README / docs if any runtime behavior differs from expectation
7. Commit and push only after validation passes

## Recommended code change queued for next cycle
Change in `run_dev_pipeline.ps1`:
- from: default `deepseek`
- to: default `gongfeng`

This is a low-risk consistency fix and should be done before more feature work.

## Status at stop
Stopped conservatively at documentation anchor because live validation, commit, and push could not be completed in this run.
