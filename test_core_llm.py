"""验证 core/llm_client.py 工蜂AI分支"""
import sys, logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
sys.path.insert(0, r'D:\AIproject\MarketRadar')

from core.llm_client import LLMClient

client = LLMClient()
info = client.get_provider_info("m1_decoder")
print("Provider info:", info)

resp = client.chat_completion(
    messages=[{"role": "user", "content": "用一句话解释什么是降准，输出纯JSON: {\"term\":\"降准\",\"effect\":\"...\",\"direction\":\"BULLISH\"}"}],
    module_name="m1_decoder"
)
print("回复:", resp)
