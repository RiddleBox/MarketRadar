"""
tests/_m0_test.py — M0 收集器测试

测试：
  1. ManualProvider：文本导入 + 标准化 + 去重 + 写入 incoming/
  2. 去重索引：重复导入被跳过
  3. 文件名格式验证
  4. RssProvider 导入（不实际抓取，仅测试实例化）
"""
import sys, tempfile
sys.path.insert(0, r"D:\AIproject\MarketRadar")

from pathlib import Path
from datetime import datetime

from m0_collector.models import RawArticle, CollectedItem
from m0_collector.dedup import DedupIndex
from m0_collector.normalizer import Normalizer
from m0_collector.providers.manual import ManualProvider
from m0_collector.providers.rss import RssProvider

tmpdir = Path(tempfile.mkdtemp())
dedup_path = tmpdir / "dedup_index.json"
incoming_dir = tmpdir / "incoming"
incoming_dir.mkdir()
print(f"测试目录: {tmpdir}\n")

# ── 测试1：ManualProvider 基本导入 ─────────────────────────
print("=" * 50)
print("测试1: ManualProvider 文本导入")
print("=" * 50)

provider = ManualProvider(source_name="测试来源")
articles = provider.fetch(
    text="""【财联社2026年4月13日讯】中国人民银行今日宣布，将7天期逆回购操作利率
从1.80%下调至1.55%，降幅25个基点，为2023年以来最大单次降息幅度。
市场反应积极，上证综指涨2.13%，北向资金净流入168.7亿元。""",
    title="央行超预期降息25bp",
    source_url="https://test.example.com/article/001",
    published_at="2026-04-13 10:00:00",
)
assert len(articles) == 1, f"应返回1条，实际{len(articles)}"
a = articles[0]
print(f"✓ provider_id={a.provider_id} | title={a.title}")
print(f"  source={a.source_name} | url={a.source_url}")

# ── 测试2：Normalizer 标准化 ────────────────────────────────
print("\n测试2: Normalizer 标准化")
print("=" * 50)

dedup = DedupIndex(dedup_path)
normalizer = Normalizer(dedup_index=dedup)
items, skipped, errors = normalizer.normalize(articles)

assert len(items) == 1, f"应标准化1条，实际{len(items)}"
assert skipped == 0
assert errors == 0

item = items[0]
print(f"✓ item_id={item.item_id}")
print(f"  filename={item.filename()}")
print(f"  published_at={item.published_at}")
print(f"  content_len={len(item.content)}")

# 验证文件名格式：YYYYMMDD_provider_hash.txt
fname = item.filename()
parts = fname.replace(".txt", "").split("_")
assert len(parts) == 3, f"文件名格式错误: {fname}"
assert parts[1] == "manual", f"provider 字段错误: {parts[1]}"
print(f"  文件名格式 ✓")

# ── 测试3：去重 ─────────────────────────────────────────────
print("\n测试3: 重复导入去重")
print("=" * 50)

items2, skipped2, _ = normalizer.normalize(articles)  # 同样内容再导入
assert len(items2) == 0, f"应被去重，实际{len(items2)}"
assert skipped2 == 1
print(f"✓ 重复导入被跳过 (skipped={skipped2})")

# force_reimport 模式
items3, skipped3, _ = normalizer.normalize(articles, force_reimport=True)
assert len(items3) == 1, f"force_reimport 应绕过去重，实际{len(items3)}"
print(f"✓ force_reimport 绕过去重 ✓")

# ── 测试4：to_text 输出格式 ─────────────────────────────────
print("\n测试4: CollectedItem.to_text() 输出格式")
print("=" * 50)

text = item.to_text()
assert "财联社" in text or "测试来源" in text
assert "央行超预期降息25bp" in text
assert "<!-- source:" in text  # 元数据注释行
print(f"✓ to_text() 包含标题、来源、元数据注释")
print(f"  前200字符:\n{text[:200]}")

# ── 测试5：写入文件 + 去重索引持久化 ───────────────────────
print("\n测试5: 写入 incoming/ + 持久化去重索引")
print("=" * 50)

fp = incoming_dir / item.filename()
fp.write_text(item.to_text(), encoding="utf-8")
dedup.save()

assert fp.exists(), f"文件未写入: {fp}"
assert dedup_path.exists(), f"去重索引未保存: {dedup_path}"

import json
idx = json.loads(dedup_path.read_text())
assert len(idx["urls"]) >= 1
print(f"✓ 文件已写入: {fp.name}")
print(f"✓ 去重索引已保存: urls={len(idx['urls'])} hashes={len(idx['hashes'])}")

# ── 测试6：RssProvider 实例化（不实际网络请求）──────────────
print("\n测试6: RssProvider 实例化")
print("=" * 50)

rss = RssProvider(feeds=[{"name": "测试", "url": "http://test.example.com/rss", "language": "zh"}])
assert rss.provider_id == "rss"
print(f"✓ RssProvider 实例化成功 | provider_id={rss.provider_id}")

# ── 汇总 ────────────────────────────────────────────────────
print("\n" + "=" * 50)
print("M0 收集器所有测试通过 ✓")
print(f"  ManualProvider: 文本导入 ✓")
print(f"  Normalizer: 标准化 + 去重 ✓")
print(f"  DedupIndex: 持久化 ✓")
print(f"  CollectedItem: to_text() + filename() ✓")
print(f"  RssProvider: 实例化 ✓")
