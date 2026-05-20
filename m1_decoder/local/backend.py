"""
m1_decoder/local/backend.py — 本地模型解码后端

两阶段流水线：
  Stage 1: Detector — 快速判断 has_event（~0.4s）
  Stage 2: Extractor — 简化 schema 提取（~3-4s）
  Stage 3: RuleEngine — 规则填充 scores/description/event_time（Python）
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import List, Optional

from core.llm_client import LLMClient
from core.schemas import MarketSignal, SourceType
from m1_decoder.backend_base import DecoderBackend
from m1_decoder.local.prompts import (
    DETECTOR_SYSTEM_PROMPT,
    DETECTOR_USER_PROMPT,
    EXTRACTOR_SYSTEM_PROMPT,
    EXTRACTOR_USER_PROMPT,
)
from m1_decoder.local.scorer import RuleBasedScorer

logger = logging.getLogger(__name__)


def _extract_json_from_response(response_text: str) -> str:
    """从 LLM 回复中提取 JSON 内容。"""
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", response_text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r"\[[\s\S]*\]", response_text)
    if m:
        return m.group(0)
    m = re.search(r"\{[\s\S]*\}", response_text)
    if m:
        return m.group(0)
    return response_text.strip()


class LocalBackend(DecoderBackend):
    """
    本地模型解码后端。

    使用 Ollama + Qwen2.5 进行两阶段信号提取：
    1. Detector：快速判断文本是否包含市场事件
    2. Extractor：提取简化 schema（8字段），不生成 scores
    3. RuleEngine：Python 规则填充剩余字段

    Usage:
        backend = LocalBackend()
        signals = backend.decode(
            raw_text="央行今日宣布下调存款准备金率0.5个百分点...",
            source_ref="https://www.pbc.gov.cn/...",
            source_type=SourceType.OFFICIAL_ANNOUNCEMENT,
            batch_id="batch_001"
        )
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        if llm_client is not None:
            self._client = llm_client
        else:
            self._client = LLMClient()
        self._scorer = RuleBasedScorer()
        logger.info("LocalBackend initialized")

    def decode(
        self,
        raw_text: str,
        source_ref: str,
        source_type: SourceType,
        batch_id: str,
    ) -> List[MarketSignal]:
        """两阶段流水线解码。"""
        if not raw_text or not raw_text.strip():
            return []

        src_type_str = source_type.value if isinstance(source_type, SourceType) else str(source_type)
        collected_time = datetime.now().isoformat()

        # ── Stage 1: Detector ──────────────────────────────────
        has_event = self._run_detector(raw_text)

        if not has_event:
            logger.info(f"Detector: no event found for batch {batch_id}")
            return []

        # ── Stage 2: Extractor ─────────────────────────────────
        raw_signals = self._run_extractor(raw_text, src_type_str)

        if not raw_signals:
            logger.info(f"Extractor: no signals parsed for batch {batch_id}")
            return []

        # ── Stage 3: Rule Engine ────────────────────────────────
        enriched = self._scorer.process(
            raw_signals,
            source_type=src_type_str,
            batch_id=batch_id,
            source_ref=source_ref,
            collected_time=collected_time,
        )

        # ── Pydantic Validation ─────────────────────────────────
        signals: List[MarketSignal] = []
        skipped = 0
        for item in enriched:
            try:
                signals.append(MarketSignal(**item))
            except Exception as e:
                error_detail = str(e)
                if hasattr(e, 'errors'):
                    error_detail = json.dumps(e.errors(), ensure_ascii=False, indent=2)
                logger.warning(
                    f"LocalBackend: skipping invalid signal:\n"
                    f"Error: {error_detail}\n"
                    f"Item: {json.dumps(item, ensure_ascii=False, indent=2)}"
                )
                skipped += 1

        if skipped > 0:
            logger.warning(f"LocalBackend: skipped {skipped} invalid signals")

        logger.info(f"LocalBackend: decoded {len(signals)} signals from batch {batch_id}")
        return signals

    # ── Stage 1 实现 ───────────────────────────────────────────

    def _run_detector(self, raw_text: str) -> bool:
        """调用 LLM 判断文本是否包含市场事件。失败时默认返回 True（降级到 extractor）。"""
        messages = [
            {"role": "system", "content": DETECTOR_SYSTEM_PROMPT},
            {"role": "user", "content": DETECTOR_USER_PROMPT.format(raw_text=raw_text)},
        ]

        try:
            response = self._client.chat_completion(
                messages=messages,
                module_name="m1_decoder",
            )
            json_str = _extract_json_from_response(response)
            result = json.loads(json_str)
            has_event = result.get("has_event", True)
            logger.debug(f"Detector result: has_event={has_event}")
            return bool(has_event)

        except Exception as e:
            logger.warning(f"Detector failed: {e}, defaulting to has_event=True")
            return True  # 降级：不确定时交给 extractor 判断

    # ── Stage 2 实现 ───────────────────────────────────────────

    def _run_extractor(self, raw_text: str, source_type: str) -> List[dict]:
        """调用 LLM 提取简化 schema 信号。失败时返回空列表。"""
        messages = [
            {"role": "system", "content": EXTRACTOR_SYSTEM_PROMPT},
            {"role": "user", "content": EXTRACTOR_USER_PROMPT.format(
                source_type=source_type,
                raw_text=raw_text,
            )},
        ]

        try:
            response = self._client.chat_completion(
                messages=messages,
                module_name="m1_decoder",
            )
            json_str = _extract_json_from_response(response)

            if not json_str or json_str.strip() in ("[]", "null", ""):
                return []

            data = json.loads(json_str)
            if isinstance(data, dict):
                signals = data.get("signals", [])
                if isinstance(signals, list):
                    return signals
                return []
            if isinstance(data, list):
                return data

            logger.warning(f"Extractor returned unexpected type: {type(data)}")
            return []

        except json.JSONDecodeError as e:
            logger.warning(f"Extractor JSON parse failed: {e}")
            return []
        except Exception as e:
            logger.error(f"Extractor LLM call failed: {e}")
            return []
