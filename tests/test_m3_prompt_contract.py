from m3_judgment.prompt_templates import STEP_B_USER_PROMPT


def test_step_b_prompt_prioritizes_core_fields_and_limits_tail_lists():
    assert "优先保证以下核心字段完整" in STEP_B_USER_PROMPT
    assert "counter_evidence` 最多 2 条" in STEP_B_USER_PROMPT
    assert "invalidation_conditions` 最多 3 条" in STEP_B_USER_PROMPT
    assert "must_watch_indicators` 最多 4 条" in STEP_B_USER_PROMPT
    assert "kill_switch_signals` 最多 3 条" in STEP_B_USER_PROMPT
    assert "warnings` 最多 2 条" in STEP_B_USER_PROMPT
    assert "不要 markdown 代码块" in STEP_B_USER_PROMPT
