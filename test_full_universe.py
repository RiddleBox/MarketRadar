#!/usr/bin/env python3
"""Test full market universe without filters"""

import sys
sys.path.insert(0, '.')

from core.schemas import Market
from m12_opportunity_catcher.stock_universe import StockUniverse

def test_full_universe():
    """Test full market stock universe"""
    print("\n" + "="*60)
    print("Full Market Universe Test")
    print("Config: No industry filter, No price filter")
    print("="*60 + "\n")

    # Create stock universe with no filters
    universe = StockUniverse(
        enable_industry_filter=False,  # All industries
        min_price_us=0.0,              # No price filter
        min_volume=100000              # Only volume filter
    )

    # Test A-share
    print("Fetching A-share stocks...")
    a_stocks = universe.get_stock_list(Market.A_SHARE)
    print(f"A-share: {len(a_stocks)} stocks")
    if a_stocks:
        print(f"Sample: {a_stocks[:5]}")

    print()

    # Test US stocks
    print("Fetching US stocks...")
    us_stocks = universe.get_stock_list(Market.US)
    print(f"US stocks: {len(us_stocks)} stocks")
    if us_stocks:
        print(f"Sample: {us_stocks[:5]}")

    print("\n" + "="*60)
    print(f"Total: {len(a_stocks) + len(us_stocks)} stocks")
    print("="*60 + "\n")

if __name__ == "__main__":
    test_full_universe()
