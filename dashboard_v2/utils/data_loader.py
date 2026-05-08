"""
MarketRadar Dashboard V2 - 数据加载层

统一管理所有数据源的加载，提供缓存和错误处理
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import streamlit as st

ROOT = Path(__file__).parent.parent.parent


# ═══════════════════════════════════════════════════════════════
# 持仓数据
# ═══════════════════════════════════════════════════════════════

@st.cache_data(ttl=15)
def load_positions_open() -> list[dict]:
    """加载当前持仓"""
    try:
        from m9_paper_trader.paper_trader import PaperTrader
        trader = PaperTrader()
        return [p.__dict__ for p in trader.list_open()]
    except Exception as e:
        st.error(f"加载持仓失败: {e}")
        return []


@st.cache_data(ttl=15)
def load_positions_closed() -> list[dict]:
    """加载已平仓记录"""
    try:
        from m9_paper_trader.paper_trader import PaperTrader
        trader = PaperTrader()
        return [p.__dict__ for p in trader.list_closed()]
    except Exception as e:
        return []


@st.cache_data(ttl=60)
def load_trade_log() -> list[dict]:
    """加载交易日志"""
    try:
        log_file = ROOT / "data" / "paper_trade_log.json"
        if log_file.exists():
            return json.loads(log_file.read_text(encoding="utf-8"))
        return []
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════
# 机会数据
# ═══════════════════════════════════════════════════════════════

@st.cache_data(ttl=30)
def load_opportunities() -> list[dict]:
    """加载机会列表"""
    try:
        opp_dir = ROOT / "data" / "opportunities"
        if not opp_dir.exists():
            return []

        opps = []
        # 修复：文件名格式是 opp_*.json，不是 opportunities_*.json
        for f in sorted(opp_dir.glob("opp_*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:100]:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    opps.extend(data)
                elif isinstance(data, dict):
                    opps.append(data)
            except Exception:
                continue

        # 去重
        seen, unique = set(), []
        for o in opps:
            oid = o.get("opportunity_id", "")
            if oid and oid not in seen:
                seen.add(oid)
                unique.append(o)

        return unique
    except Exception as e:
        st.error(f"加载机会失败: {e}")
        return []


# ═══════════════════════════════════════════════════════════════
# 信号数据
# ═══════════════════════════════════════════════════════════════

@st.cache_data(ttl=30)
def load_signals_recent(days: int = 7) -> list[dict]:
    """加载最近N天的信号"""
    try:
        from m2_storage.signal_store import SignalStore
        store = SignalStore()
        sigs = store.get_by_time_range(
            start=datetime.now() - timedelta(days=days),
            end=datetime.now(),
        )
        return [s.model_dump(mode="json") for s in sigs]
    except Exception as e:
        st.error(f"加载信号失败: {e}")
        return []


@st.cache_data(ttl=30)
def load_signal_by_id(signal_id: str) -> dict | None:
    """根据ID加载单个信号的完整信息"""
    try:
        from m2_storage.signal_store import SignalStore
        store = SignalStore()
        signal = store.get_by_id(signal_id)
        return signal.model_dump(mode="json") if signal else None
    except Exception:
        return None


@st.cache_data(ttl=30)
def load_signal_stats() -> dict:
    """加载信号统计"""
    try:
        from m2_storage.signal_store import SignalStore
        return SignalStore().stats()
    except Exception:
        return {"total": 0}


# ═══════════════════════════════════════════════════════════════
# 情绪数据
# ═══════════════════════════════════════════════════════════════

@st.cache_data(ttl=60)
def load_sentiment_latest() -> dict | None:
    """加载最新情绪快照"""
    try:
        from m10_sentiment.sentiment_store import SentimentStore
        import json
        store = SentimentStore()
        snapshots = store.latest(1)
        if not snapshots:
            return None

        raw = snapshots[0]

        # 解析 raw_json 获取完整数据
        raw_data = json.loads(raw.get("raw_json", "{}"))

        # 从 raw_json 中获取正确的中文标签
        sentiment_label = raw_data.get("sentiment_label", raw.get("label", "中性"))

        # 映射字段名以匹配 Dashboard 期望
        return {
            "timestamp": raw.get("snapshot_time", ""),
            "fear_greed_index": raw.get("fear_greed", 50),
            "sentiment_label": sentiment_label,
            "direction": raw.get("direction", "NEUTRAL"),
            "intensity": _compute_intensity(raw.get("fear_greed", 50)),
            "northbound_flow": {
                "net_inflow": raw.get("northbound_flow", 0),
                "shanghai": 0,  # 数据库中没有分项数据
                "shenzhen": 0,
            },
            "sector_sentiment": _extract_sector_sentiment(raw_data),
        }
    except Exception as e:
        st.error(f"加载情绪数据失败: {e}")
        return None


def _compute_intensity(fear_greed: float) -> float:
    """计算情绪强度 (1-10)"""
    deviation = abs(fear_greed - 50)
    return round(2.0 + (deviation / 50) * 8.0, 1)


def _extract_sector_sentiment(raw_data: dict) -> dict:
    """从百度热搜提取板块情绪（简化版）"""
    # 从百度热搜股票中提取，作为热门板块的代理指标
    hot_stocks = raw_data.get("baidu_hot_stocks", [])
    if not hot_stocks:
        return {}

    # 简化处理：将热搜股票的热度归一化为情绪值
    max_heat = max([h for _, h in hot_stocks[:5]], default=1)
    sector_data = {}
    for stock, heat in hot_stocks[:5]:
        # 归一化到 0-100
        sentiment_score = (heat / max_heat) * 100 if max_heat > 0 else 50
        # 使用股票名称（已经是字符串）
        sector_data[str(stock)] = round(sentiment_score, 1)

    return sector_data


@st.cache_data(ttl=60)
def load_sentiment_history(n: int = 48) -> list[dict]:
    """加载情绪历史"""
    try:
        from m10_sentiment.sentiment_store import SentimentStore
        import json
        store = SentimentStore()
        raw_history = store.latest(n)

        # 映射字段名
        history = []
        for raw in raw_history:
            # 从 raw_json 中获取正确的中文标签
            raw_data = json.loads(raw.get("raw_json", "{}"))
            sentiment_label = raw_data.get("sentiment_label", raw.get("label", "中性"))

            history.append({
                "timestamp": raw.get("snapshot_time", ""),
                "fear_greed_index": raw.get("fear_greed", 50),
                "sentiment_label": sentiment_label,
                "direction": raw.get("direction", "NEUTRAL"),
            })

        return history
    except Exception:
        return []


@st.cache_data(ttl=60)
def load_sentiment_trend(n: int = 20) -> dict:
    """加载情绪趋势统计"""
    try:
        from m10_sentiment.sentiment_store import SentimentStore
        store = SentimentStore()
        return store.trend(n)
    except Exception:
        return {}


# ═══════════════════════════════════════════════════════════════
# 调度器数据
# ═══════════════════════════════════════════════════════════════

@st.cache_data(ttl=20)
def load_scheduler_state() -> dict:
    """加载调度器状态"""
    try:
        state_file = ROOT / "data" / "scheduler_state.json"
        if not state_file.exists():
            return {"running": False, "tasks": {}, "recent_runs": []}
        return json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:
        return {"running": False, "tasks": {}, "recent_runs": []}


# ═══════════════════════════════════════════════════════════════
# 决策数据
# ═══════════════════════════════════════════════════════════════

@st.cache_data(ttl=30)
def load_decision_records(date_str: str | None = None) -> list[dict]:
    """加载决策记录"""
    try:
        from pipeline.decision_log import DecisionLog
        dl = DecisionLog()
        target = date_str or dl.today
        data = dl.load_decisions(target)
        return data if isinstance(data, list) else []
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════
# M13调研数据
# ═══════════════════════════════════════════════════════════════

@st.cache_data(ttl=30)
def load_m13_cache_stats() -> dict:
    """加载M13缓存统计"""
    try:
        cache_dir = ROOT / "data" / "research_cache"
        if not cache_dir.exists():
            return {"total": 0, "valid": 0, "expired": 0}

        from m13_research.cache_manager import CacheManager
        cache_mgr = CacheManager(str(cache_dir))

        total = 0
        valid = 0
        expired = 0
        now = datetime.now()

        for cache_file in cache_dir.glob("*.json"):
            total += 1
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                cached_at = datetime.fromisoformat(data.get("cached_at", ""))
                ttl_hours = data.get("ttl_hours", 24)
                if (now - cached_at).total_seconds() / 3600 < ttl_hours:
                    valid += 1
                else:
                    expired += 1
            except Exception:
                expired += 1

        return {"total": total, "valid": valid, "expired": expired}
    except Exception as e:
        st.error(f"加载M13缓存统计失败: {e}")
        return {"total": 0, "valid": 0, "expired": 0}


@st.cache_data(ttl=30)
def load_m13_recent_research(limit: int = 20) -> list[dict]:
    """加载最近的调研记录"""
    try:
        cache_dir = ROOT / "data" / "research_cache"
        if not cache_dir.exists():
            return []

        records = []
        for cache_file in sorted(cache_dir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)[:limit]:
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                records.append({
                    "symbol": data.get("symbol", ""),
                    "level": data.get("level", ""),
                    "cached_at": data.get("cached_at", ""),
                    "ttl_hours": data.get("ttl_hours", 24),
                    "confidence_delta": data.get("result", {}).get("confidence_delta", 0),
                    "key_findings": data.get("result", {}).get("key_findings", []),
                })
            except Exception:
                continue

        return records
    except Exception as e:
        st.error(f"加载M13调研记录失败: {e}")
        return []


@st.cache_data(ttl=60)
def load_m13_stats() -> dict:
    """加载M13调研统计"""
    try:
        cache_dir = ROOT / "data" / "research_cache"
        if not cache_dir.exists():
            return {
                "total_research": 0,
                "by_level": {"QUICK": 0, "STANDARD": 0, "DEEP": 0},
                "avg_confidence_delta": 0.0,
            }

        total = 0
        by_level = {"QUICK": 0, "STANDARD": 0, "DEEP": 0}
        confidence_deltas = []

        for cache_file in cache_dir.glob("*.json"):
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                total += 1
                level = data.get("level", "STANDARD")
                by_level[level] = by_level.get(level, 0) + 1

                delta = data.get("result", {}).get("confidence_delta", 0)
                if delta != 0:
                    confidence_deltas.append(delta)
            except Exception:
                continue

        avg_delta = sum(confidence_deltas) / len(confidence_deltas) if confidence_deltas else 0.0

        return {
            "total_research": total,
            "by_level": by_level,
            "avg_confidence_delta": round(avg_delta, 3),
        }
    except Exception as e:
        st.error(f"加载M13统计失败: {e}")
        return {
            "total_research": 0,
            "by_level": {"QUICK": 0, "STANDARD": 0, "DEEP": 0},
            "avg_confidence_delta": 0.0,
        }


# ═══════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════

def clear_all_cache():
    """清除所有缓存"""
    st.cache_data.clear()


def get_summary_stats() -> dict:
    """获取总览统计数据"""
    return {
        "positions_count": len(load_positions_open()),
        "opportunities_count": len(load_opportunities()),
        "signals_count": load_signal_stats().get("total", 0),
        "scheduler_running": load_scheduler_state().get("running", False),
    }
