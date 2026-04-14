from backtest.market_price_resolver import get_market_price_plan


def test_market_price_plan_for_a_share_prefers_local_then_baostock_then_akshare():
    plan = get_market_price_plan("A_SHARE")
    assert plan.market == "A_SHARE"
    assert plan.source_priority[0] == "price_cache"
    assert "akshare" in plan.source_priority


def test_market_price_plan_for_hk_prefers_local_then_akshare():
    plan = get_market_price_plan("HK")
    assert plan.market == "HK"
    assert plan.source_priority[0] == "price_cache"
    assert "akshare" in plan.source_priority
