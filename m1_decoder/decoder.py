"""
m1_decoder/decoder.py — 信号解码主逻辑

从原始文本中提取结构化 MarketSignal 列表。
核心流程：构建 Prompt → 调用 LLM → 解析 JSON → Pydantic 校验 → 补充元数据
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import List, Optional

from core.llm_client import LLMClient, get_default_client
from core.schemas import MarketSignal, SourceType
from m1_decoder.prompt_templates import SYSTEM_PROMPT, SIGNAL_EXTRACTION_PROMPT

logger = logging.getLogger(__name__)

# 最大重试次数（JSON 解析失败时重试）
MAX_PARSE_RETRIES = 2


def _extract_json_from_response(response_text: str) -> str:
    """
    从 LLM 回复中提取 JSON 内容。
    LLM 有时会在 JSON 前后添加说明文字或 markdown 代码块。
    """
    # 尝试提取 ```json ... ``` 代码块
    json_block_pattern = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
    match = json_block_pattern.search(response_text)
    if match:
        return match.group(1).strip()

    # 尝试直接找到 JSON 数组
    array_pattern = re.compile(r"\[[\s\S]*\]")
    match = array_pattern.search(response_text)
    if match:
        return match.group(0)

    # 如果找不到，返回原始响应（可能是空列表或纯 JSON）
    return response_text.strip()


def _parse_signals_from_json(
    json_str: str,
    batch_id: str,
    source_ref: str,
    source_type: SourceType,
) -> List[MarketSignal]:
    """
    解析 LLM 返回的 JSON 字符串为 MarketSignal 列表。
    进行 Pydantic 校验，丢弃无效信号并记录警告。
    """
    try:
        raw_data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON from LLM: {e}\nRaw response:\n{json_str[:500]}")

    if not isinstance(raw_data, list):
        raise ValueError(f"Expected JSON array, got {type(raw_data).__name__}")

    signals: List[MarketSignal] = []
    skipped = 0

    for i, item in enumerate(raw_data):
        try:
            # 补充系统字段（LLM 不应该生成这些）
            item["batch_id"] = batch_id
            item["source_ref"] = source_ref
            item["source_type"] = source_type.value if isinstance(source_type, SourceType) else source_type

            # 设置采集时间
            if "collected_time" not in item:
                item["collected_time"] = datetime.now().isoformat()

            signal = MarketSignal(**item)
            signals.append(signal)
            logger.debug(f"Parsed signal {i+1}: {signal.signal_label}")

        except Exception as e:
            logger.warning(
                f"Skipping invalid signal at index {i}: {e}\n"
                f"Raw item: {json.dumps(item, ensure_ascii=False)[:200]}"
            )
            skipped += 1

    if skipped > 0:
        logger.warning(f"Skipped {skipped} invalid signals out of {len(raw_data)} total")

    return signals


class SignalDecoder:
    """
    M1 信号解码器。

    将原始文本（新闻、研报、公告等）解码为结构化的 MarketSignal 列表。

    Usage:
        decoder = SignalDecoder()
        signals = decoder.decode(
            raw_text="央行今日宣布下调存款准备金率0.5个百分点...",
            source_ref="https://www.pbc.gov.cn/...",
            source_type=SourceType.OFFICIAL_ANNOUNCEMENT,
            batch_id="batch_20241115_001"
        )
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        """
        Args:
            llm_client: LLM 客户端实例。None 则使用全局默认客户端。
        """
        self._client = llm_client or get_default_client()
        logger.info("SignalDecoder initialized")

    def decode(
        self,
        raw_text: str,
        source_ref: str,
        source_type: SourceType,
        batch_id: str,
    ) -> List[MarketSignal]:
        """
        从原始文本中解码市场信号。

        Args:
            raw_text: 原始文本内容（新闻/研报/公告等）
            source_ref: 来源引用（URL/标题/报告名称）
            source_type: 来源类型枚举
            batch_id: 批次ID，用于追踪

        Returns:
            MarketSignal 列表，可能为空（空列表是合法的正确答案）

        Raises:
            RuntimeError: LLM 调用失败且重试次数耗尽
        """
        if not raw_text or not raw_text.strip():
            logger.warning("Empty input text, returning empty signal list")
            return []

        # 构建 Prompt
        user_prompt = SIGNAL_EXTRACTION_PROMPT.format(
            source_ref=source_ref,
            source_type=source_type.value if isinstance(source_type, SourceType) else source_type,
            batch_id=batch_id,
            process_time=datetime.now().isoformat(),
            raw_text=raw_text.strip(),
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # 调用 LLM（含重试逻辑），解析失败时自动降级
        last_response: Optional[str] = None

        for attempt in range(1, MAX_PARSE_RETRIES + 2):
            try:
                logger.info(
                    f"Decoding signals: batch={batch_id}, source={source_ref[:50]}, "
                    f"text_len={len(raw_text)}, attempt={attempt}"
                )

                # 第二次以后追加错误修正提示
                if attempt > 1 and last_response:
                    correction_prompt = (
                        f"你上次的回复无法解析为有效 JSON：\n{last_response[:200]}\n\n"
                        f"请重新输出，只返回 JSON 数组，不要任何其他文字。"
                        f"如果没有有效信号，返回 `[]`。"
                    )
                    messages.append({"role": "assistant", "content": last_response})
                    messages.append({"role": "user", "content": correction_prompt})

                response = self._client.chat_completion(
                    messages=messages,
                    module_name="m1_decoder",
                )
                last_response = response

                # 提取并解析 JSON
                json_str = _extract_json_from_response(response)

                # 处理空响应
                if not json_str or json_str.strip() in ("[]", "null", ""):
                    logger.info(f"No signals found in batch {batch_id}")
                    return []

                signals = _parse_signals_from_json(
                    json_str,
                    batch_id=batch_id,
                    source_ref=source_ref,
                    source_type=source_type,
                )

                logger.info(
                    f"Successfully decoded {len(signals)} signals "
                    f"from batch {batch_id}"
                )
                return signals

            except ValueError as e:
                # JSON 解析错误，可以重试
                logger.warning(
                    f"JSON parse error on attempt {attempt}: {e}. "
                    f"{'Retrying...' if attempt <= MAX_PARSE_RETRIES else 'Giving up.'}"
                )
                if attempt > MAX_PARSE_RETRIES:
                    # 最终降级：返回空列表，不要让整个 pipeline 崩溃
                    logger.error(
                        f"Failed to parse LLM response after {MAX_PARSE_RETRIES + 1} attempts. "
                        f"Returning empty signal list for batch {batch_id}."
                    )
                    return []

            except RuntimeError as e:
                # LLM 调用失败（已经在 llm_client 中重试过了）
                logger.error(f"LLM call failed for batch {batch_id}: {e}")
                raise

        return []

    def decode_file(
        self,
        file_path,
        source_ref: str,
        source_type: SourceType,
        batch_id: str,
        max_chunk_chars: int = 6000,
    ) -> List[MarketSignal]:
        """
        从文件路径解码信号，自动分块处理超长文本。

        Args:
            file_path: 文件路径（str 或 Path）
            source_ref: 来源引用
            source_type: 来源类型
            batch_id: 批次 ID
            max_chunk_chars: 每块最大字符数（默认 6000）

        Returns:
            MarketSignal 列表
        """
        from pathlib import Path
        from pipeline.ingest import split_text_into_chunks

        text = Path(file_path).read_text(encoding="utf-8")
        chunks = split_text_into_chunks(text, max_chars=max_chunk_chars)

        all_signals: List[MarketSignal] = []
        for i, chunk in enumerate(chunks):
            chunk_ref = f"{source_ref}#chunk{i+1}" if len(chunks) > 1 else source_ref
            signals = self.decode(
                raw_text=chunk,
                source_ref=chunk_ref,
                source_type=source_type,
                batch_id=batch_id,
            )
            all_signals.extend(signals)

        logger.info(f"decode_file: {len(chunks)} chunks → {len(all_signals)} signals")
        return all_signals

    def decode_batch(
        self,
        texts: List[dict],
        batch_id: str,
    ) -> List[MarketSignal]:
        """
        批量解码多个文本。

        Args:
            texts: 文本列表，每个元素包含 'text', 'source_ref', 'source_type'
            batch_id: 批次ID

        Returns:
            所有文本解码出的 MarketSignal 合并列表
        """
        all_signals: List[MarketSignal] = []

        for i, item in enumerate(texts):
            try:
                signals = self.decode(
                    raw_text=item["text"],
                    source_ref=item.get("source_ref", f"unknown_source_{i}"),
                    source_type=SourceType(item.get("source_type", "news")),
                    batch_id=batch_id,
                )
                all_signals.extend(signals)
            except Exception as e:
                logger.error(f"Failed to decode item {i} in batch {batch_id}: {e}")
                # 单条失败不中断整批处理

        logger.info(
            f"Batch decode complete: {len(texts)} texts → {len(all_signals)} signals"
        )
        return all_signals
