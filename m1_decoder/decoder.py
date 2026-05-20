"""
m1_decoder/decoder.py — M1 信号解码器（Facade）

根据配置 m1_decoder_mode 路由到不同后端：
- "api" → APIBackend（Claude API，现有逻辑不变）
- "local" → LocalBackend（Ollama + Qwen，两阶段流水线）

下游模块无感知，两者输出相同的 List[MarketSignal]。
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List, Optional

from core.schemas import MarketSignal, SourceType

logger = logging.getLogger(__name__)


def _read_m1_mode_from_config() -> str:
    """从配置文件读取 m1_decoder_mode。返回 "api" 或 "local"，默认 "api"。"""
    import yaml

    config_paths = [
        Path(os.getcwd()) / "config" / "llm_config.yaml",
        Path(__file__).resolve().parent.parent / "config" / "llm_config.yaml",
    ]

    config = {}
    for cp in config_paths:
        if cp.exists():
            with open(cp, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            break

    # 合并本地覆盖
    for cp in config_paths:
        local_path = cp.parent / "llm_config.local.yaml"
        if local_path.exists():
            with open(local_path, encoding="utf-8") as f:
                local_config = yaml.safe_load(f) or {}
            config.update(local_config)
            break

    mode = config.get("m1_decoder_mode", "api")
    if mode not in ("api", "local"):
        logger.warning(f"Unknown m1_decoder_mode='{mode}', falling back to 'api'")
        return "api"
    return mode


class SignalDecoder:
    """
    M1 信号解码器（Facade）。

    根据 m1_decoder_mode 配置自动选择后端：
    - api: 使用云端 Claude（现有逻辑）
    - local: 使用本地 Ollama + Qwen（两阶段流水线）

    Usage:
        decoder = SignalDecoder()
        signals = decoder.decode(
            raw_text="央行今日宣布下调存款准备金率0.5个百分点...",
            source_ref="https://www.pbc.gov.cn/...",
            source_type=SourceType.OFFICIAL_ANNOUNCEMENT,
            batch_id="batch_001"
        )
    """

    def __init__(self, llm_client=None, mode: Optional[str] = None):
        """
        Args:
            llm_client: LLM 客户端实例。显式传入时强制使用 API 后端（向后兼容测试 mock）。
            mode: "api" 或 "local"。None 则从配置文件读取。
        """
        self._backend = self._create_backend(llm_client, mode)

    def _create_backend(self, llm_client, mode):
        from m1_decoder.backend_api import APIBackend
        from m1_decoder.local.backend import LocalBackend

        if mode is not None:
            if mode == "api":
                return APIBackend(llm_client)
            elif mode == "local":
                return LocalBackend(llm_client)
            else:
                raise ValueError(f"Unknown mode: {mode}")

        detected_mode = _read_m1_mode_from_config()
        logger.info(f"SignalDecoder: detected mode={detected_mode}")
        if detected_mode == "local":
            return LocalBackend(llm_client)
        else:
            if llm_client is not None:
                return APIBackend(llm_client)
            return APIBackend()

    # ── 委托方法 ──────────────────────────────────────────────

    def decode(
        self,
        raw_text: str,
        source_ref: str,
        source_type: SourceType,
        batch_id: str,
    ) -> List[MarketSignal]:
        return self._backend.decode(raw_text, source_ref, source_type, batch_id)

    def decode_file(
        self,
        file_path,
        source_ref: str,
        source_type: SourceType,
        batch_id: str,
        max_chunk_chars: int = 6000,
    ) -> List[MarketSignal]:
        return self._backend.decode_file(file_path, source_ref, source_type, batch_id, max_chunk_chars)

    def decode_batch(
        self,
        texts: List[dict],
        batch_id: str,
    ) -> List[MarketSignal]:
        return self._backend.decode_batch(texts, batch_id)
