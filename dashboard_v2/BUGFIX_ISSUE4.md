# 问题4修复：情绪面页面采集后没数据

## 问题描述
情绪面页面点击"立即采集"后，采集任务成功执行，但页面刷新后仍显示"暂无情绪数据"。

## 根本原因
1. **数据未写入数据库**：`SentimentEngine._save_snapshot()` 方法只将数据保存为 JSON 文件，没有调用 `SentimentStore.save()` 写入数据库
2. **Dashboard 读取数据库**：`load_sentiment_latest()` 从数据库读取数据，而不是 JSON 文件
3. **中文编码问题**：SQLite 连接未设置 UTF-8 编码，导致中文标签乱码

## 修复方案

### 1. 在 `SentimentEngine._save_snapshot()` 中添加数据库保存

**文件**: `m10_sentiment/sentiment_engine.py`

```python
def _save_snapshot(self, snap, signal, batch_id: str):
    """保存原始快照到 data/sentiment/ 和数据库"""
    try:
        # ... 保存 JSON 文件的代码 ...
        
        # 同时保存到数据库（新增）
        from m10_sentiment.sentiment_store import SentimentStore
        store = SentimentStore()
        store.save(data)
        logger.info(f"[SentimentEngine] 快照已写入数据库")
    except Exception as e:
        logger.warning(f"[SentimentEngine] 快照保存失败: {e}")
```

### 2. 修复 SQLite 中文编码问题

**文件**: `m10_sentiment/sentiment_store.py`

```python
def _init_db(self):
    with sqlite3.connect(self.db_path) as conn:
        conn.text_factory = str  # 设置文本工厂
        conn.execute("PRAGMA encoding = 'UTF-8'")  # 设置 UTF-8 编码
        # ... 创建表的代码 ...
```

## 验证结果

### 采集前
```python
>>> store.stats()
{'total_snapshots': 0, 'extreme_count': 0, 'avg_fear_greed': 50.0, 'latest_snapshot': None}
```

### 采集后
```python
>>> store.stats()
{'total_snapshots': 1, 'extreme_count': 0, 'avg_fear_greed': 66.7, 'latest_snapshot': '2026-05-06T22:32:45.508671'}

>>> store.latest(1)
[{
    'id': 1,
    'snapshot_time': '2026-05-06T22:32:45.508671',
    'fear_greed': 66.65,
    'label': '贪婪',  # 中文正常显示
    'direction': 'BULLISH',
    'northbound_flow': 0.0,
    'adr': 0.7595,
    'avg_score': 64.74,
    'high_score_cnt': 1257
}]
```

## 影响文件
- `m10_sentiment/sentiment_engine.py` - 添加数据库保存逻辑
- `m10_sentiment/sentiment_store.py` - 修复 UTF-8 编码

## 测试步骤
1. 访问情绪面页面
2. 点击"🔄 立即采集"按钮
3. 等待采集完成（约1分钟）
4. 页面自动刷新，确认显示情绪数据：
   - 恐贪指数
   - 市场情绪标签
   - 方向（看多/看空/中性）
   - 强度
   - 恐贪指数仪表盘
   - 情绪趋势图

## 关于市场分类

**问题**: 情绪分析是否应该分市场（A股/港股/美股）？

**当前实现**: 情绪采集主要针对 A 股市场，因为：
- 北向资金流向：专指外资通过沪深港通买入 A 股
- 涨跌家数统计：基于 A 股市场
- 百度热搜、微博情绪：主要关注 A 股标的

**未来改进方向**:
1. 为港股和美股添加独立的情绪指标
2. 在 Dashboard 添加市场选择器
3. 调度器中为不同市场设置独立的采集任务

---

**修复时间**: 2026-05-06 22:35
**状态**: ✅ 已修复并验证
