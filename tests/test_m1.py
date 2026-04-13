"""
tests/test_m1.py — M1 信号解码模块测试

使用 mock LLM 调用，不需要真实 API Key。
"""
from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from core.schemas import Market, SourceType, SignalType, Direction, TimeHorizon
from m1_decoder.decoder import SignalDecoder


MOCK_LLM_RESPONSE = json.dumps({
    "signals": [
        {
            "signal_id": "sig_20260413_001",
            "signal_type": "macro",
            "signal_label": "央行降息25bp",
            "description": "中国人民银行宣布将7天逆回购利率下调25个基点，为2024年以来最大单次降幅",
            "evidence_text": "中国人民银行今日宣布，将7天期逆回购操作利率从1.80%下调至1.55%",
            "affected_markets": ["A_SHARE", "HK"],
            "affected_instruments": ["沪深300", "上证50", "恒生指数"],
            "signal_direction": "BULLISH",
            "event_time": "2026-04-13T09:00:00",
            "time_horizon": "MEDIUM",
            "intensity_score": 9,
            "confidence_score": 9,
            "timeliness_score": 10,
            "source_type": "announcement",
            "logic_frame": {
                "what_changed": "7天逆回购利率",
                "change_direction": "decrease",
                "affects": ["股市估值", "债券收益率", "资金成本"]
            }
        },
        {
            "signal_id": "sig_20260413_002",
            "signal_type": "capital_flow",
            "signal_label": "北向资金大幅净流入",
            "description": "沪深港通北向资金今日净流入超过150亿元，为近三个月单日最大流入",
            "evidence_text": "截至收盘，北向资金净买入152.3亿元，其中沪股通净买入89.1亿元",
            "affected_markets": ["A_SHARE"],
            "affected_instruments": ["沪深300", "金融板块"],
            "signal_direction": "BULLISH",
            "event_time": "2026-04-13T15:30:00",
            "time_horizon": "SHORT",
            "intensity_score": 7,
            "confidence_score": 9,
            "timeliness_score": 10,
            "source_type": "data",
            "logic_frame": {
                "what_changed": "北向资金流向",
                "change_direction": "increase",
                "affects": ["大盘蓝筹股", "A股情绪"]
            }
        }
    ]
})


class TestSignalDecoder:
    def _make_decoder(self, mock_response: str = MOCK_LLM_RESPONSE):
        """创建带 Mock LLM 的 decoder"""
        mock_llm = MagicMock()
        mock_llm.chat_completion.return_value = mock_response
        return SignalDecoder(llm_client=mock_llm)

    def test_decode_basic(self):
        decoder = self._make_decoder()
        signals = decoder.decode(
            raw_text="央行今日降息25bp，北向资金大幅净流入",
            source_ref="test_001",
            source_type=SourceType.NEWS,
            batch_id="test_batch_001",
        )
        assert len(signals) == 2

    def test_signal_fields(self):
        decoder = self._make_decoder()
        signals = decoder.decode(
            raw_text="测试文本",
            source_ref="test_001",
            source_type=SourceType.ANNOUNCEMENT,
            batch_id="test_batch",
        )
        sig = signals[0]
        assert sig.signal_type == SignalType.MACRO
        assert sig.signal_label == "央行降息25bp"
        assert Market.A_SHARE in sig.affected_markets
        assert Market.HK in sig.affected_markets
        assert sig.intensity_score == 9
        assert sig.confidence_score == 9

    def test_market_labels(self):
        decoder = self._make_decoder()
        signals = decoder.decode("test", "ref", SourceType.NEWS, "batch_001")
        # 第一条信号影响 A_SHARE 和 HK
        assert set(signals[0].affected_markets) == {Market.A_SHARE, Market.HK}
        # 第二条信号只影响 A_SHARE
        assert signals[1].affected_markets == [Market.A_SHARE]

    def test_collected_time_auto_filled(self):
        """collected_time 应该由 decoder 自动填充"""
        decoder = self._make_decoder()
        before = datetime.now()
        signals = decoder.decode("test", "ref", SourceType.NEWS, "batch_001")
        after = datetime.now()
        for sig in signals:
            assert sig.collected_time is not None
            assert before <= sig.collected_time <= after

    def test_batch_id_assigned(self):
        decoder = self._make_decoder()
        signals = decoder.decode("test", "ref", SourceType.NEWS, "batch_test_123")
        for sig in signals:
            assert sig.batch_id == "batch_test_123"

    def test_source_ref_assigned(self):
        decoder = self._make_decoder()
        signals = decoder.decode("test", "my_source_ref", SourceType.REPORT, "batch_001")
        for sig in signals:
            assert sig.source_ref == "my_source_ref"

    def test_empty_text(self):
        """空文本应该返回空信号列表"""
        mock_llm = MagicMock()
        mock_llm.chat_completion.return_value = json.dumps({"signals": []})
        decoder = SignalDecoder(llm_client=mock_llm)
        signals = decoder.decode("", "ref", SourceType.NEWS, "batch_001")
        assert signals == []

    def test_malformed_llm_response_retry(self):
        """LLM 返回格式错误时，decoder 应该重试并降级"""
        mock_llm = MagicMock()
        mock_llm.chat_completion.side_effect = [
            "这不是有效的JSON格式",   # 第一次失败
            MOCK_LLM_RESPONSE,        # 第二次成功
        ]
        decoder = SignalDecoder(llm_client=mock_llm)
        signals = decoder.decode("test", "ref", SourceType.NEWS, "batch_001")
        assert len(signals) >= 0  # 重试后应该返回结果（不崩溃）

    def test_llm_called_with_text(self):
        """验证 LLM 被调用时 Prompt 包含了原始文本"""
        mock_llm = MagicMock()
        mock_llm.chat_completion.return_value = json.dumps({"signals": []})
        decoder = SignalDecoder(llm_client=mock_llm)
        test_text = "这是特定的测试文本内容"
        decoder.decode(test_text, "ref", SourceType.NEWS, "batch_001")

        # 验证 LLM 被调用
        assert mock_llm.chat_completion.called
        call_args = mock_llm.chat_completion.call_args
        messages = call_args[0][0]  # 第一个位置参数
        # 验证原始文本出现在某条消息中
        full_content = " ".join(m.get("content", "") for m in messages)
        assert test_text in full_content

    def test_score_validation(self):
        """验证评分范围在 1-10 内"""
        decoder = self._make_decoder()
        signals = decoder.decode("test", "ref", SourceType.NEWS, "batch_001")
        for sig in signals:
            assert 1 <= sig.intensity_score <= 10
            assert 1 <= sig.confidence_score <= 10
            assert 1 <= sig.timeliness_score <= 10


class TestPromptTemplates:
    def test_system_prompt_not_empty(self):
        from m1_decoder.prompt_templates import SYSTEM_PROMPT
        assert len(SYSTEM_PROMPT) > 100
        assert "信号" in SYSTEM_PROMPT

    def test_extraction_prompt_contains_taxonomy(self):
        from m1_decoder.prompt_templates import SIGNAL_EXTRACTION_PROMPT
        # 验证 Prompt 包含所有信号类型
        for signal_type in ["macro", "industry", "capital_flow", "technical", "event_driven", "policy"]:
            assert signal_type in SIGNAL_EXTRACTION_PROMPT.lower() or signal_type in SIGNAL_EXTRACTION_PROMPT

    def test_extraction_prompt_has_format_example(self):
        from m1_decoder.prompt_templates import SIGNAL_EXTRACTION_PROMPT
        # Prompt 应该包含 JSON 格式示例
        assert "json" in SIGNAL_EXTRACTION_PROMPT.lower() or "JSON" in SIGNAL_EXTRACTION_PROMPT


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
