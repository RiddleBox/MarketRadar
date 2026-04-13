import os, sys
sys.path.insert(0, r'D:\AIproject\MarketRadar')
os.environ['DEEPSEEK_API_KEY'] = 'sk-6c899392de5444369b4518e8c64aa940'

from core.llm_client import LLMClient
from core.schemas import SourceType
from m1_decoder.decoder import SignalDecoder

TEXT = '''
人民银行今日宣布一揽子宽松货币政策，具体内容包括：
1. 下调存款准备金率0.5个百分点，释放长期流动性约1万亿元
2. 下调7天期逆回购操作利率0.2个百分点
3. 引导贷款市场报价利率（LPR）和存款利率同步下调
4. 降低存量房贷利率，平均降幅约0.5个百分点
分析人士认为，此次货币政策超出市场预期，A股市场将于明日开盘交易。
'''

client = LLMClient()
client._config['default_provider'] = 'deepseek'
print(client.get_provider_info('m1_decoder'))
resp = client.chat_completion(messages=[{'role':'user','content':'只回答ok'}], module_name='m1_decoder', max_tokens=20)
print('PING=', resp)

decoder = SignalDecoder(llm_client=client)
signals = decoder.decode(TEXT, source_ref='test', source_type=SourceType.OFFICIAL_ANNOUNCEMENT, batch_id='test_deepseek_m1')
print('SIGNALS=', len(signals))
for s in signals:
    print(s.signal_type, s.signal_label, s.signal_direction, s.intensity_score, s.confidence_score)
