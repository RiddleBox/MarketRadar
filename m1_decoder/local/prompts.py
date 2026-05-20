"""
m1_decoder/local/prompts.py — 本地模型精简版 Prompt 模板

针对 Qwen2.5:1.5B 优化：极简、无歧义、低 token 消耗。
两阶段流水线：Detector（二分类）→ Extractor（简化 schema）。
"""

# ═══════════════════════════════════════════════════════════════
# Stage 1: 信号存在性检测（Detector）
# ═══════════════════════════════════════════════════════════════

DETECTOR_SYSTEM_PROMPT = (
    "你是一个市场事件检测器。只判断文本是否包含已发生的、有明确证据的市场事件。"
    '回复格式：{"has_event": true} 或 {"has_event": false}'
)

DETECTOR_USER_PROMPT = "此文本是否包含已发生的市场事件？\n\n文本：{raw_text}\n\n回复JSON："


# ═══════════════════════════════════════════════════════════════
# Stage 2: 结构化字段提取（Extractor）
# ═══════════════════════════════════════════════════════════════

EXTRACTOR_SYSTEM_PROMPT = (
    "你是市场信号提取助手。从文本中提取已发生的市场事件。\n"
    "规则：\n"
    "- 禁止预测、观点、建议、推测\n"
    "- evidence_text 必须逐字复制原文连续片段\n"
    "- signal_type 只选一个: macro, industry, capital_flow, technical, event_driven, policy, sentiment, anomalous_activity\n"
    "- signal_direction 只选一个: BULLISH, BEARISH, NEUTRAL, UNCERTAIN\n"
    "- time_horizon 只选一个: SHORT, MEDIUM, LONG\n"
    "- logic_frame 必须包含 what_changed, change_direction, affects 三个字段\n"
    "- 无有效信号返回 []"
)

EXTRACTOR_USER_PROMPT = """从文本提取市场信号。每个字段只选一个值，不要多选。无信号返回 []。

signal_type（只选1个）: macro | industry | capital_flow | technical | event_driven | policy | sentiment | anomalous_activity
direction（只选1个）: BULLISH | BEARISH | NEUTRAL | UNCERTAIN
markets: ["A_SHARE"] 或 ["HK"] 或 ["US"]
time_horizon（只选1个）: SHORT | MEDIUM | LONG
source_type: {source_type}

输出JSON数组：
[{{"signal_type":"event_driven","signal_label":"简短标签","evidence_text":"原文引用","affected_markets":["A_SHARE"],"signal_direction":"BULLISH","time_horizon":"MEDIUM","source_type":"{source_type}","logic_frame":{{"what_changed":"已发生事实","change_direction":"BULLISH","affects":["相关标的"]}}}}]

方向参考：BULLISH=利好, BEARISH=利空, NEUTRAL=中性, UNCERTAIN=不明

文本：
{raw_text}"""
