"""
backtest/market_price_resolver.py — Market-aware price source resolver

目标：
- 为 reality backtest 提供最小的按市场价格源分流能力
- 先在 backtest 层落地，不大改 core.data_loader
- 当前优先覆盖 A_SHARE / HK 的 source priority 摘要与可用性检查
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

import yaml

ROOT = Path(__file__).resolve().parents[1]
MARKET_CONFIG = ROOT / "config" / "market_config.yaml"


@dataclass
class MarketPricePlan:
    market: str
    source_priority: List[str]
    notes: str = ""


def _load_market_config() -> dict:
    if not MARKET_CONFIG.exists():
        return {}
    return yaml.safe_load(MARKET_CONFIG.read_text(encoding="utf-8")) or {}


def get_market_price_plan(market: str) -> MarketPricePlan:
    cfg = _load_market_config()
    market_cfg = (cfg.get("markets") or {}).get(market, {}) if isinstance(cfg, dict) else {}
    data_sources = market_cfg.get("data_sources") or {}
    sources = data_sources.get("priority") if isinstance(data_sources, dict) else data_sources

    # 对 reality backtest 的最小规则收敛：本地沉淀优先，在线源兜底
    normalized = [str(s).lower().replace("csv_local", "csv") for s in (sources or [])]
    if market == "A_SHARE":
        preferred = ["csv", "baostock", "akshare"]
        merged = [s for s in preferred if s in normalized]
        for extra in normalized:
            if extra not in merged:
                merged.append(extra)
        return MarketPricePlan(
            market=market,
            source_priority=["price_cache"] + merged,
            notes="A_SHARE 优先本地缓存/CSV，其次 baostock，最后 akshare。",
        )

    if market == "HK":
        preferred = ["csv", "akshare"]
        merged = [s for s in preferred if s in normalized]
        for extra in normalized:
            if extra not in merged:
                merged.append(extra)
        return MarketPricePlan(
            market=market,
            source_priority=["price_cache"] + merged,
            notes="HK 优先本地缓存/CSV，当前在线兜底以 akshare 为主。",
        )

    return MarketPricePlan(
        market=market,
        source_priority=["price_cache"] + normalized,
        notes="默认沿用 market_config 配置。",
    )
