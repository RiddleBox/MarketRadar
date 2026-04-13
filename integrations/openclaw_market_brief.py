"""
integrations/openclaw_market_brief.py — OpenClaw 市场情绪分析入口

这是 MarketRadar 与 OpenClaw 对话界面的桥接层。
当用户在 OpenClaw（企业微信/工蜂AI）中说：
  "帮我分析今天市场情绪"
  "现在能抄底吗"
  "关税冲击下市场怎么看"

OpenClaw 调用 get_market_brief() 或 analyze_event()，
拿到结构化分析结果后以自然语言回复用户。

LLM 模式：OpenClaw 自身模型（工蜂AI claude-sonnet），
通过 OpenClaw 的内置 HTTP API 推理，无需额外 API key。
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent

# ── OpenClaw LLM Client（调用工蜂AI）────────────────────────

class OpenClawLLMClient:
    """
    通过 OpenClaw Gateway 本地端口调用工蜂AI模型。

    原理：OpenClaw Gateway 在本地暴露 OpenAI 兼容 API（默认 http://localhost:3000），
    agent 内部可以直接调用，无需额外认证。

    若 Gateway 不可用，自动降级到规则模式（不崩溃）。
    """

    def __init__(self):
        self.base_url = os.environ.get(
            "OPENCLAW_API_URL", "http://localhost:3000/v1"
        )
        self.model = os.environ.get(
            "OPENCLAW_MODEL", "gongfeng/claude-sonnet-4-6"
        )
        self._client = None
        self._available = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            import httpx
            self._client = httpx.Client(
                base_url=self.base_url,
                timeout=30.0,
                headers={"Content-Type": "application/json"},
            )
            return self._client
        except ImportError:
            logger.warning("[OpenClawLLM] httpx 未安装，降级到规则模式")
            return None

    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        client = self._get_client()
        if client is None:
            self._available = False
            return False
        try:
            resp = client.get("/models", timeout=3.0)
            self._available = resp.status_code == 200
        except Exception:
            self._available = False
        return self._available

    def chat_completion(self, messages: list, **kwargs) -> str:
        """调用工蜂AI，返回文本，失败时抛异常（让上层决定是否降级）"""
        client = self._get_client()
        if client is None:
            raise RuntimeError("httpx 未安装")
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", 800),
            "temperature": kwargs.get("temperature", 0.3),
        }
        resp = client.post("/chat/completions", json=payload, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


# ── 市场情绪分析入口 ─────────────────────────────────────────

class MarketBriefAnalyzer:
    """
    MarketRadar 与 OpenClaw 的对话桥接。

    主要方法：
        get_market_brief()    — 获取今日市场情绪简报（自动读 M10 最新快照）
        analyze_event(desc)   — 针对特定事件快速分析
        quick_verdict(text)   — 极简问答（能不能操作 / 风险等级）
    """

    def __init__(self, use_llm: bool = True):
        self.llm = OpenClawLLMClient()
        self.use_llm = use_llm and self.llm.is_available()
        if use_llm and not self.llm.is_available():
            logger.info("[MarketBrief] OpenClaw LLM 不可用，使用规则模式")

    # ── 主入口 ──────────────────────────────────────────────

    def get_market_brief(self, market: str = "A_SHARE") -> str:
        """
        今日市场情绪简报（Markdown 格式，直接可回复给用户）

        流程：
          1. 读取 M10 最新情绪快照
          2. 构建 MarketInput，运行 AgentNetwork
          3. 格式化为中文简报
        """
        snapshot = self._load_latest_snapshot()
        market_input = self._build_market_input(snapshot, market=market)
        dist = self._run_simulation(market_input)
        return self._format_brief(dist, snapshot, market_input)

    def analyze_event(self, event_desc: str, market: str = "A_SHARE") -> str:
        """
        针对特定事件的快速分析

        用法：analyze_event("央行宣布降准50bp") → Markdown 分析报告
        """
        snapshot = self._load_latest_snapshot()
        market_input = self._build_market_input(
            snapshot, market=market, event_description=event_desc
        )
        # 如果有 LLM，让 M11 的 Agent 也用 LLM 推理
        dist = self._run_simulation(market_input, use_llm_for_agents=self.use_llm)

        # 额外：用 OpenClaw LLM 对结果做自然语言解读
        if self.use_llm:
            return self._llm_interpret(dist, event_desc, snapshot)
        return self._format_brief(dist, snapshot, market_input, event_desc=event_desc)

    def quick_verdict(self, question: str) -> str:
        """
        极简问答，返回一句话结论 + 风险等级

        例：quick_verdict("现在能买入 510300 吗？") →
           "⚠️ 建议观望 | 风险等级: 中 | 情绪中性（FG=47），无明显方向信号"
        """
        snapshot = self._load_latest_snapshot()
        market_input = self._build_market_input(snapshot)
        dist = self._run_simulation(market_input)

        fg = snapshot.get("fear_greed_index", 50.0) if snapshot else 50.0
        direction = dist.direction
        intensity = dist.intensity

        risk_level = self._assess_risk(fg, direction, intensity)
        verdict = self._one_line_verdict(direction, fg, intensity)

        return f"{verdict} | 风险等级: {risk_level} | FG={fg:.0f} 强度{intensity:.1f}/10"

    # ── 内部方法 ─────────────────────────────────────────────

    def _load_latest_snapshot(self) -> Optional[dict]:
        """从 M10 SentimentStore 读取最新快照"""
        try:
            from m10_sentiment.sentiment_store import SentimentStore
            store = SentimentStore()
            snap = store.latest()
            if snap:
                return snap if isinstance(snap, dict) else snap.__dict__
        except Exception as e:
            logger.debug(f"[MarketBrief] 读取快照失败: {e}")

        # 降级：扫描 JSON 文件
        snap_dir = ROOT / "data" / "sentiment"
        if snap_dir.exists():
            files = sorted(snap_dir.glob("snapshot_*.json"), reverse=True)
            if files:
                try:
                    return json.loads(files[0].read_text(encoding="utf-8"))
                except Exception:
                    pass
        return None

    def _build_market_input(
        self,
        snapshot: Optional[dict],
        market: str = "A_SHARE",
        event_description: str = "",
    ):
        from m11_agent_sim.schemas import (
            MarketInput, PriceContext, SentimentContext, SignalContext
        )

        if snapshot:
            sentiment = SentimentContext(
                fear_greed_index=snapshot.get("fear_greed_index", 50.0),
                sentiment_label=snapshot.get("sentiment_label", "中性"),
                northbound_flow=snapshot.get("northbound_net_billion", 0.0),
                advance_decline_ratio=snapshot.get("advance_decline_ratio", 0.5),
                weibo_sentiment=snapshot.get("weibo_sentiment", 0.0),
            )
        else:
            sentiment = SentimentContext()

        # 尝试从价格缓存获取最新价格
        price = self._load_latest_price("510300.SH")

        return MarketInput(
            timestamp=datetime.now(),
            market=market,
            event_description=event_description or "今日市场情绪分析",
            sentiment=sentiment,
            price=price,
            signals=self._load_recent_signals(),
        )

    def _load_latest_price(self, instrument: str = "510300.SH"):
        """尝试从 M9 价格缓存加载最新价格"""
        from m11_agent_sim.schemas import PriceContext
        try:
            from m9_paper_trader.price_feed import PriceFeed
            feed = PriceFeed()
            price = feed.get_current_price(instrument)
            if price:
                return PriceContext(
                    instrument=instrument,
                    current_price=price,
                )
        except Exception:
            pass
        return PriceContext()

    def _load_recent_signals(self):
        """从 M2 加载最近24小时信号作为背景"""
        from m11_agent_sim.schemas import SignalContext
        try:
            from m2_storage.signal_store import SignalStore
            store = SignalStore()
            from datetime import timedelta
            since = datetime.now() - timedelta(hours=24)
            signals = store.get_by_time_range(since, datetime.now())
            if signals:
                bullish = sum(1 for s in signals if s.direction == "BULLISH")
                bearish = sum(1 for s in signals if s.direction == "BEARISH")
                avg_intensity = sum(s.intensity_score for s in signals) / len(signals)
                return SignalContext(
                    bullish_count=bullish,
                    bearish_count=bearish,
                    neutral_count=len(signals) - bullish - bearish,
                    avg_intensity=avg_intensity,
                    avg_confidence=6.0,
                    dominant_signal_type=signals[0].signal_type if signals else "market_data",
                )
        except Exception:
            pass
        return SignalContext()

    def _run_simulation(
        self, market_input, use_llm_for_agents: bool = False
    ):
        from m11_agent_sim.agent_network import AgentNetwork

        # 如果 OpenClaw LLM 可用且要求用，传入 LLM client 给 Agent
        llm_client = None
        if use_llm_for_agents:
            llm_client = self.llm

        net = AgentNetwork._default_a_share(
            use_llm=use_llm_for_agents,
            llm_client=llm_client,
        )
        return net.run(market_input)

    def _llm_interpret(self, dist, event_desc: str, snapshot: Optional[dict]) -> str:
        """用 OpenClaw LLM 对 AgentNetwork 结果做自然语言解读"""
        fg = snapshot.get("fear_greed_index", 50.0) if snapshot else 50.0
        nb = snapshot.get("northbound_net_billion", 0.0) if snapshot else 0.0

        agent_summary = "\n".join(
            f"  - {o.agent_name}: {o.direction} 多{o.bullish_prob:.0%} — {o.reasoning}"
            for o in dist.agent_outputs
        )

        prompt = f"""你是一个专业的A股投资助手。以下是 MarketRadar 系统对市场情绪的模拟分析结果，请用简洁的中文给出投资参考建议（3~5句话，不超过200字）。

事件背景：{event_desc}

量化情绪数据：
- 恐贪指数：{fg:.1f}/100
- 北向资金：{nb:+.1f}亿
- 综合方向：{dist.direction}（多方概率 {dist.bullish_prob:.0%}，空方 {dist.bearish_prob:.0%}）
- 情绪强度：{dist.intensity:.1f}/10，置信度：{dist.confidence:.0%}

各Agent判断：
{agent_summary}

请给出：①市场当前处于什么状态 ②主要风险点 ③短线操作建议（非个人投资建议，仅供参考）"""

        try:
            messages = [
                {"role": "system", "content": (
                    "你是专业的量化投资分析助手，熟悉A股"
                    "市场特点，擅长将量化信号转化为通俗易懂的投资参考，"
                    "回答简洁专业，必须注明：仅供参考，不构成投资建议。"
                )},
                {"role": "user", "content": prompt},
            ]
            interpretation = self.llm.chat_completion(messages)
            return self._format_brief_with_interpretation(dist, fg, nb, event_desc, interpretation)
        except Exception as e:
            logger.warning(f"[MarketBrief] LLM 解读失败: {e}，降级到规则格式")
            return self._format_brief(dist, snapshot, None, event_desc=event_desc)

    def _format_brief(self, dist, snapshot: Optional[dict], market_input, event_desc: str = "") -> str:
        """规则模式下的标准格式化输出"""
        fg = snapshot.get("fear_greed_index", 50.0) if snapshot else 50.0
        nb = snapshot.get("northbound_net_billion", 0.0) if snapshot else 0.0
        adr = snapshot.get("advance_decline_ratio", 0.5) if snapshot else 0.5
        ts = snapshot.get("timestamp", datetime.now().isoformat()) if snapshot else ""
        ts_str = ts[:16].replace("T", " ") if ts else datetime.now().strftime("%Y-%m-%d %H:%M")

        dir_zh = {"BULLISH": "偏多 📈", "BEARISH": "偏空 📉", "NEUTRAL": "震荡 🔄"}
        dir_emoji = dir_zh.get(dist.direction, dist.direction)

        fg_color = (
            "🔴极度贪婪" if fg >= 80 else
            "🟠贪婪" if fg >= 60 else
            "⚪中性" if fg >= 40 else
            "🔵恐惧" if fg >= 20 else
            "🔷极度恐惧"
        )

        op_advice = self._operation_advice(fg, dist.direction, dist.intensity)

        lines = [
            f"## 📊 MarketRadar 市场情绪简报",
            f"**更新时间**：{ts_str}",
            f"{('**事件**：' + event_desc) if event_desc else ''}",
            "",
            f"### 综合判断：{dir_emoji}",
            f"| 指标 | 数值 |",
            f"|------|------|",
            f"| 恐贪指数 | {fg:.1f} {fg_color} |",
            f"| 多方概率 | {dist.bullish_prob:.0%} |",
            f"| 空方概率 | {dist.bearish_prob:.0%} |",
            f"| 情绪强度 | {dist.intensity:.1f}/10 |",
            f"| 置信度 | {dist.confidence:.0%} |",
            f"| 北向资金 | {nb:+.1f}亿 |",
            f"| 涨跌比 | {adr:.0%} |",
            "",
            f"### Agent 分析链",
        ]
        for o in dist.agent_outputs:
            bar = "█" * int(o.bullish_prob * 10) + "░" * (10 - int(o.bullish_prob * 10))
            lines.append(
                f"- **{o.agent_name}**：{o.direction} [{bar}] 多{o.bullish_prob:.0%} — {o.reasoning}"
            )

        lines += [
            "",
            f"### 操作参考",
            op_advice,
            "",
            f"> ⚠️ 仅供参考，不构成投资建议。由 MarketRadar M11 规则模式生成。",
        ]
        return "\n".join(l for l in lines if l is not None)

    def _format_brief_with_interpretation(self, dist, fg, nb, event_desc, interpretation) -> str:
        """LLM 模式下带 AI 解读的输出"""
        dir_zh = {"BULLISH": "偏多 📈", "BEARISH": "偏空 📉", "NEUTRAL": "震荡 🔄"}

        lines = [
            f"## 📊 MarketRadar · 工蜂AI 市场情绪分析",
            f"**事件**：{event_desc}" if event_desc else "",
            f"**综合判断**：{dir_zh.get(dist.direction, dist.direction)} | 多方 {dist.bullish_prob:.0%} · 空方 {dist.bearish_prob:.0%} · 置信 {dist.confidence:.0%}",
            f"**情绪数据**：FG={fg:.0f} · 北向 {nb:+.1f}亿",
            "",
            "### 🤖 AI 解读",
            interpretation,
            "",
            "### 各Agent判断",
        ]
        for o in dist.agent_outputs:
            lines.append(f"- **{o.agent_name}**：{o.direction} 多{o.bullish_prob:.0%} — {o.reasoning}")

        lines.append("\n> ⚠️ 仅供参考，不构成投资建议。由 MarketRadar M11 + 工蜂AI 联合生成。")
        return "\n".join(l for l in lines if l is not None)

    def _operation_advice(self, fg: float, direction: str, intensity: float) -> str:
        if fg >= 80:
            return "🚨 **极度贪婪区**：追涨风险极高，存量持仓考虑分批减仓，空仓者不宜追入。"
        if fg <= 20:
            if direction == "BULLISH":
                return "💡 **极度恐惧 + 政策看多**：逆向机会窗口，可小仓试探，严格止损。"
            return "⛔ **极度恐惧**：市场仍在寻底，保持观望，等待企稳信号。"
        if direction == "BULLISH" and intensity >= 7:
            return "✅ **多方信号较强**：趋势向好，可适度参与，注意仓位控制（≤30%）。"
        if direction == "BEARISH" and intensity >= 7:
            return "⚠️ **空方信号较强**：规避风险，降低仓位，等待做空信号确认。"
        return "⚖️ **信号中性**：市场方向不明，建议观望或保持轻仓，等待更清晰信号。"

    def _one_line_verdict(self, direction: str, fg: float, intensity: float) -> str:
        if direction == "BULLISH" and intensity >= 7:
            return "✅ 可适度参与"
        if direction == "BEARISH" and intensity >= 7:
            return "⚠️ 建议规避"
        if fg <= 20:
            return "💡 极度恐惧，留意逆向"
        if fg >= 80:
            return "🚨 极度贪婪，谨慎追涨"
        return "⚖️ 建议观望"

    def _assess_risk(self, fg: float, direction: str, intensity: float) -> str:
        if fg >= 80 or (direction == "BEARISH" and intensity >= 8):
            return "高"
        if fg <= 20 or intensity >= 7:
            return "中高"
        if intensity >= 5:
            return "中"
        return "低"


# ── 便捷函数（OpenClaw 直接调用）────────────────────────────

_analyzer: Optional[MarketBriefAnalyzer] = None


def _get_analyzer() -> MarketBriefAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = MarketBriefAnalyzer()
    return _analyzer


def market_brief(market: str = "A_SHARE") -> str:
    """今日市场情绪简报（一行调用）"""
    return _get_analyzer().get_market_brief(market)


def analyze_event(event_desc: str, market: str = "A_SHARE") -> str:
    """事件快速分析（一行调用）"""
    return _get_analyzer().analyze_event(event_desc, market)


def quick_verdict(question: str) -> str:
    """极简问答（一行调用）"""
    return _get_analyzer().quick_verdict(question)
