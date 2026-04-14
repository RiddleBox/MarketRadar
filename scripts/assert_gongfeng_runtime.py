from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.llm_client import LLMClient  # noqa: E402

REQUIRED_PROVIDER = "gongfeng"
REQUIRED_MODEL = "gongfeng/gpt-5-4"
MODULES = ["default", "m1_decoder", "m3_judgment", "m4_action", "m6_retrospective"]


def main() -> int:
    client = LLMClient()
    failed = False
    for module in MODULES:
        info = client.get_provider_info(module)
        provider = info.get("provider")
        model = info.get("model")
        print(f"{module}: provider={provider} model={model} credential_ready={info.get('credential_ready')}")
        if provider != REQUIRED_PROVIDER or model != REQUIRED_MODEL:
            failed = True
    if failed:
        print("\nRUNTIME_ASSERT_FAILED: provider/model drift detected", file=sys.stderr)
        return 1
    print("\nRUNTIME_ASSERT_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
