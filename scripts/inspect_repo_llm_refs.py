import os
import re

root = r"D:\AIproject\MarketRadar"
pat = re.compile(r"provider|llm_config|LLMClient\(|default_provider|claude|anthropic|deepseek|gongfeng/gpt-5-4|OPENAI_BASE_URL|XFYUN_API_KEY|DEEPSEEK_API_KEY", re.I)

for dp, _, fs in os.walk(root):
    for f in fs:
        if f.endswith((".py", ".yaml", ".yml", ".md", ".env", ".txt", ".ps1")):
            p = os.path.join(dp, f)
            try:
                with open(p, "r", encoding="utf-8") as fh:
                    for i, line in enumerate(fh, 1):
                        if pat.search(line):
                            print(f"{p}:{i}:{line.rstrip()}")
            except Exception:
                pass
