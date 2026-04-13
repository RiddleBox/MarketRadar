from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.llm_client import LLMClient  # noqa: E402


def main() -> int:
    client = LLMClient()
    modules = ["default", "m1_decoder", "m3_judgment", "m4_action", "m6_retrospective"]
    report = {
        "config_path": str(ROOT / "config" / "llm_config.yaml"),
        "default_provider": client._config.get("default_provider"),
        "modules": {m: client.get_provider_info(m) for m in modules},
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
