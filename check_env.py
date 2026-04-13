import os
keys = ['DEEPSEEK_API_KEY','XFYUN_API_KEY','ANTHROPIC_API_KEY','OPENAI_API_KEY','OPENAI_BASE_URL']
print({k: (bool(os.environ.get(k)) and not str(os.environ.get(k)).startswith('${')) for k in keys})
