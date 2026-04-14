from m4_action.strategy_registry import STRATEGY_REGISTRY, get_strategy_spec, list_strategy_specs


def test_strategy_registry_contains_seed_specs():
    assert "MacroMomentum" in STRATEGY_REGISTRY
    assert "PolicyBreakout" in STRATEGY_REGISTRY
    assert "ComboFilter" in STRATEGY_REGISTRY


def test_get_strategy_spec_returns_expected_shape():
    spec = get_strategy_spec("MacroMomentum")
    assert spec is not None
    assert spec.style == "macro_momentum"
    assert "macro" in spec.allowed_signal_types
    assert spec.risk_profile["stop_loss_pct"] == 0.05


def test_list_strategy_specs_returns_all_specs():
    names = {spec.name for spec in list_strategy_specs()}
    assert {"MacroMomentum", "PolicyBreakout", "ComboFilter"}.issubset(names)
