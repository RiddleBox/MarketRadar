import sys
sys.path.insert(0, r'D:\AIproject\MarketRadar')
from core.llm_client import LLMClient

c = LLMClient()
print(c.get_provider_info('m1_decoder'))
try:
    r = c.chat_completion(
        messages=[{'role': 'user', 'content': '返回 JSON: {"ok": true, "msg": "hello"}'}],
        module_name='m1_decoder',
        max_tokens=80,
    )
    print(r)
except Exception as e:
    print('ERR:', e)
