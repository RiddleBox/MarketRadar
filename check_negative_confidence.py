import json
from pathlib import Path

opps = list(Path('data/opportunities').glob('*.json'))
print(f'Total opportunities: {len(opps)}')

neg_conf = []
for f in opps[:100]:
    try:
        data = json.load(open(f, encoding='utf-8'))
        conf = data['opportunity_score']['confidence_score']
        if conf < 0:
            neg_conf.append((f.name, conf, data['priority_level'], data.get('opportunity_title', 'N/A')))
    except Exception as e:
        print(f'Error reading {f.name}: {e}')

print(f'\nNegative confidence opportunities: {len(neg_conf)}')
for name, conf, pri, title in neg_conf[:10]:
    print(f'  {name}: conf={conf:.3f}, priority={pri}, title={title[:50]}')
