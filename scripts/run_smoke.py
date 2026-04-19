"""
scripts/run_smoke.py — 主链路 smoke test

用法:
    python scripts/run_smoke.py

验证 M1→M2→M3→M4 端到端联调，含完整断言。
需要 LLM provider 可用（通过 config/llm_config.local.yaml 配置）。
"""
import sys
import tempfile
from pathlib import Path
from datetime import datetime

# 确保项目根目录在 sys.path 中
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from core.llm_client import LLMClient
from m1_decoder.decoder import SignalDecoder
from m2_storage.signal_store import SignalStore
from m3_judgment.judgment_engine import JudgmentEngine
from m4_action.action_designer import ActionDesigner
from core.schemas import SourceType

BATCH_ID = f"smoke_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

TEST_TEXT = """【财联社2024年9月24日讯】中国人民银行今日宣布，下调存款准备金率0.5个百分点，释放长期流动性约1万亿元。同时下调7天期逆回购操作利率20个基点。受此影响，A股市场大幅反弹，沪深300指数单日涨幅超过4%，北向资金净流入超200亿元。"""


def main():
    errors = []

    # ── LLM 连通性 ────────────────────────────────────────────
    print("=" * 60)
    print("Smoke Test: 主链路端到端验证")
    print("=" * 60)

    try:
        llm = LLMClient()
        provider = llm._config.get("default_provider", "unknown")
        print(f"[LLM] default_provider = {provider}")
    except Exception as e:
        print(f"[FAIL] LLMClient 初始化失败: {e}")
        return 1

    # ── M1 信号解码 ────────────────────────────────────────────
    print(f"\n[M1] 信号解码中...")
    try:
        decoder = SignalDecoder(llm_client=llm)
        signals = decoder.decode(
            raw_text=TEST_TEXT,
            source_ref="smoke_test",
            source_type=SourceType.NEWS,
            batch_id=BATCH_ID,
        )
        assert len(signals) >= 1, f"M1 应提取至少1条信号，实际 {len(signals)}"
        print(f"  OK - signals: {len(signals)}")
        for s in signals:
            print(f"    {s.signal_label} | {s.signal_type.value} | {s.signal_direction} | I={s.intensity_score}")
    except Exception as e:
        print(f"  FAIL M1 失败: {e}")
        errors.append(f"M1: {e}")

    # ── M2 信号存储 ────────────────────────────────────────────
    if not errors:
        print(f"\n[M2] 信号存储中...")
        try:
            import m2_storage.signal_store as ss_mod
            orig_db = ss_mod.DB_FILE
            tmpdir = Path(tempfile.mkdtemp())
            ss_mod.DB_FILE = tmpdir / "smoke_signals.db"
            store = SignalStore()
            store.save(signals)
            loaded = store.get_by_batch(BATCH_ID)
            assert len(loaded) >= 1, f"M2 应返回至少1条信号，实际 {len(loaded)}"
            print(f"  OK 存入并检索: {len(loaded)} 条")
            ss_mod.DB_FILE = orig_db
        except Exception as e:
            print(f"  FAIL M2 失败: {e}")
            errors.append(f"M2: {e}")

    # ── M3 机会判断 ────────────────────────────────────────────
    if not errors:
        print(f"\n[M3] 机会判断中...")
        try:
            judge = JudgmentEngine(llm_client=llm)
            opps = judge.judge(signals=loaded, batch_id=BATCH_ID)
            print(f"  OK 机会数量: {len(opps)}")
            for o in opps:
                print(f"    [{o.priority_level.value}] {o.opportunity_title}")
                print(f"    评分: 综合={o.opportunity_score.overall_score} 催化剂={o.opportunity_score.catalyst_strength}")
        except Exception as e:
            print(f"  FAIL M3 失败: {e}")
            errors.append(f"M3: {e}")

    # ── M4 行动设计 ────────────────────────────────────────────
    if not errors and opps:
        print(f"\n[M4] 行动设计中...")
        try:
            designer = ActionDesigner(llm_client=llm)
            plan = designer.design(opps[0])
            assert plan.stop_loss is not None, "M4 必须输出止损"
            print(f"  OK 标的: {plan.primary_instruments[:3]}")
            print(f"    止损={plan.stop_loss.stop_loss_value}% 止盈={plan.take_profit.take_profit_value}%")
            print(f"    仓位={plan.position_sizing.suggested_allocation}")
        except Exception as e:
            print(f"  FAIL M4 失败: {e}")
            errors.append(f"M4: {e}")
    elif not errors and not opps:
        print(f"\n[M4] 跳过（M3 输出空列表，这是合法行为）")

    # ── 结果 ────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    if errors:
        print(f"SMOKE TEST FAILED ({len(errors)} 个错误)")
        for e in errors:
            print(f"  FAIL {e}")
        return 1
    else:
        print("SMOKE TEST PASSED OK")
        return 0


if __name__ == "__main__":
    sys.exit(main())
