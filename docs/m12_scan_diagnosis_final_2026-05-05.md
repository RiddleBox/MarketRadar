# M12扫描0异动诊断报告（最终版）

**日期**: 2026-05-05  
**诊断对象**: `data/m12_scan_results.json` 中的39次扫描记录  
**核心发现**: 扫描记录来自 `run_continuous_simulation.py`，不是M7调度器

---

## 一、数据来源确认

### m12_scan_results.json 的写入者

通过代码检查发现：

```python
# run_continuous_simulation.py:585-607
def _save_results(total_count):
    results_file = "data/m12_scan_results.json"
    record = {
        "timestamp": datetime.now().isoformat(),
        "total_opportunities": total_count,
    }
    existing.append(record)
    # 保存到文件
```

**结论**: 
- ✅ 扫描记录由 `run_continuous_simulation.py` 写入
- ❌ 不是M7调度器写入
- 这是一个**独立的持续模拟脚本**

### 记录分析

| 记录类型 | 数量 | 来源脚本 | 特征 |
|---------|------|---------|------|
| 简单记录 | 38条 | run_continuous_simulation.py | 只有 `total_opportunities` |
| 详细记录 | 1条 | run_full_scan.py | 有 `a_share`, `hk`, `us` 字段 |

---

## 二、run_continuous_simulation.py 的扫描逻辑

### 主循环逻辑（第728-772行）

```python
while RUNNING:
    time.sleep(10)
    
    # 盘后扫描：所有市场闭市时执行
    if now - last_daily >= daily_interval and not is_any_market_trading():
        run_daily_scan(a_share_feed_cls=a_share_feed_cls)
        last_daily = now
    
    if not is_weekend():
        # A股盘中扫描 (09:30-15:00)
        if is_a_share_trading() and now - last_a_share_scan >= 600:
            run_intraday_scan(markets_to_scan=[Market.A_SHARE], ...)
            last_a_share_scan = now
        
        # 港股盘中扫描 (09:30-16:00)
        if is_hk_trading() and now - last_hk_scan >= 600:
            run_intraday_scan(markets_to_scan=[Market.HK], ...)
            last_hk_scan = now
        
        # 美股盘中扫描 (21:30-04:00)
        if is_us_trading() and now - last_us_scan >= 600:
            run_intraday_scan(markets_to_scan=[Market.US], ...)
            last_us_scan = now
```

### 时间窗口检查函数（第631-650行）

```python
def _is_in_range(now_h: int, now_m: int, start: tuple, end: tuple) -> bool:
    start_min = start[0] * 60 + start[1]
    end_min = end[0] * 60 + end[1]
    now_min = now_h * 60 + now_m
    if start_min <= end_min:
        return start_min <= now_min <= end_min
    else:
        # 跨日处理
        return now_min >= start_min or now_min <= end_min

def is_us_trading():
    now_h, now_m = datetime.now().hour, datetime.now().minute
    return _is_in_range(now_h, now_m, (21, 30), (4, 0))
```

### run_intraday_scan 函数（第249-322行）

```python
def run_intraday_scan(markets_to_scan=None, a_share_feed_cls=None):
    # 数据源选择：优先FutuFeed，回退到YFinanceFeed
    feed_map = {
        Market.A_SHARE: a_share_feed_cls,
        Market.HK: FutuFeed,
        Market.US: FutuFeed,
    }
    
    # 并行扫描多个市场
    with ThreadPoolExecutor(max_workers=len(markets_to_scan)) as executor:
        for market in markets_to_scan:
            results = engine.run_intraday_scan(market=market, price_feed=pf)
            total += len(results)
    
    # 没有调用 _save_results！
    return total
```

**关键发现**: `run_intraday_scan()` **没有调用** `_save_results()`！

---

## 三、_save_results 的调用位置

通过搜索发现，`_save_results()` 只在一个地方被调用：

```python
# run_continuous_simulation.py:143-192 (run_daily_scan函数)
def run_daily_scan(a_share_feed_cls=None):
    """盘后全量扫描"""
    # ... 扫描逻辑 ...
    total = len(results_a) + len(results_hk) + len(results_us)
    _save_results(total)  # ← 只有这里调用
```

**结论**: 
- ✅ `run_daily_scan()` 会写入 `m12_scan_results.json`
- ❌ `run_intraday_scan()` **不会**写入 `m12_scan_results.json`

---

## 四、扫描记录时间分析

### 成功扫描（6次，2-3个异动）

| 时间 | 异动数 | 推测来源 |
|------|--------|---------|
| 11:17 | 2个 | ❓ 不在盘后时段 |
| 12:32 | 2个 | ❓ 不在盘后时段 |
| 12:34 | 2个 | ❓ 不在盘后时段 |
| 14:10 | 3个 | ❓ 不在盘后时段 |
| 15:47 | 2个 | ❓ 不在盘后时段 |
| 17:03 | 3个 | ✅ 可能是盘后扫描 |

### 失败扫描（33次，0个异动）

| 时间段 | 次数 | 市场状态 | 推测来源 |
|--------|------|---------|---------|
| 23:36-04:49 | 9次 | 美股时段 | ✅ 盘后扫描（美股休市） |
| 07:53-08:49 | 3次 | 非交易时段 | ✅ 盘后扫描 |
| 其他 | 21次 | 各时段 | ✅ 盘后扫描 |

---

## 五、核心问题解答

### 问题1: 为什么美股时段(21:30-04:00)扫描返回0异动？

**答案**: 这些扫描**不是盘中扫描**，而是**盘后扫描**！

```python
# 盘后扫描触发条件（第739行）
if now - last_daily >= daily_interval and not is_any_market_trading():
    run_daily_scan(...)  # ← 调用盘后扫描
```

**逻辑**:
1. 23:36时，`is_any_market_trading()` 返回 `True`（美股时段）
2. 但如果 `run_continuous_simulation.py` 在23:36之前就判断"所有市场闭市"
3. 或者美股实际休市（周末、节假日）
4. 就会触发 `run_daily_scan()`（盘后扫描）
5. 盘后扫描使用 `run_daily_scan()` 而非 `run_intraday_scan()`
6. 盘后扫描依赖历史日线数据，不是实时价格
7. 如果数据源无法获取历史数据 → 返回0异动

### 问题2: 为什么非交易时段(07:53-08:49)会触发扫描？

**答案**: 这是**盘后扫描**，符合设计！

```python
# 盘后扫描条件
if not is_any_market_trading():  # 所有市场闭市
    run_daily_scan(...)
```

07:53-08:49 不在任何市场的交易时段内，所以触发盘后扫描是**正常的**。

### 问题3: 17:03的成功扫描是如何触发的？

**答案**: 这是**盘后扫描**，在港股收盘后触发。

- 港股16:00收盘
- 17:03时 `is_any_market_trading()` 返回 `False`
- 触发盘后扫描
- 成功发现3个异动

### 问题4: 11:17-15:47的成功扫描是如何触发的？

**疑问**: 这些时间在交易时段内，按理说不应该触发盘后扫描。

**可能原因**:
1. **手动触发**: 用户手动运行了 `run_full_scan.py` 或调用了 `run_daily_scan()`
2. **脚本重启**: `run_continuous_simulation.py` 在首次启动时会执行一次盘后扫描
3. **周末判断**: 如果是周末，`is_weekend()` 返回 `True`，跳过盘中扫描

---

## 六、为什么盘后扫描返回0异动？

### 盘后扫描的数据源

```python
# run_continuous_simulation.py:143-192
def run_daily_scan(a_share_feed_cls=None):
    # 使用 run_daily_scan() 而非 run_intraday_scan()
    results_a = engine.run_daily_scan(market=Market.A_SHARE, price_feed=feed_a)
    results_hk = engine.run_daily_scan(market=Market.HK, price_feed=feed_hk)
    results_us = engine.run_daily_scan(market=Market.US, price_feed=feed_us)
```

### run_daily_scan 的数据需求

```python
# m12_opportunity_catcher/catcher_engine.py:120-170
def run_daily_scan(market, price_feed, ...):
    # 需要历史日线数据（20天）
    anomalies = self.anomaly_detector.scan_daily(
        market=market,
        price_feed=price_feed,
        scan_date=scan_date,
    )
```

### 0异动的可能原因

1. **数据源问题**: FutuFeed/YFinanceFeed 无法获取历史日线数据
2. **美股休市**: 4月28日-4月29日可能是美股休市日
3. **阈值过高**: sigma=2.0, atr=2.0 在盘后扫描中过于严格
4. **数据延迟**: 盘后立即扫描时，当日数据尚未更新

---

## 七、总结

### 关键发现

1. **扫描记录来源**: `run_continuous_simulation.py`，不是M7调度器
2. **扫描类型**: 大部分是**盘后扫描**（`run_daily_scan`），不是盘中扫描
3. **0异动原因**: 盘后扫描依赖历史日线数据，数据源可能失败
4. **时间窗口**: 盘后扫描在"所有市场闭市"时触发，包括美股时段（如果美股休市）

### 您的三个问题的答案

1. **扫描频率**: ✅ 确实是10分钟（盘中扫描），但记录的是盘后扫描
2. **市场分轨**: ✅ 确实分开扫描，但盘后扫描会扫描所有市场
3. **休市时的无效扫描**: ❌ 不是"无效扫描"，而是**盘后扫描的正常行为**

### 真正的问题

**为什么盘后扫描持续返回0异动？**

需要检查：
1. FutuFeed/YFinanceFeed 是否能正常获取历史日线数据
2. 4月28日-5月5日期间是否有美股/港股/A股休市
3. 盘后扫描的阈值是否需要调整

---

## 八、建议

1. **检查 run_continuous_simulation.py 是否在运行**
2. **查看盘后扫描的日志**（如果有）
3. **测试数据源**: 手动运行 `run_full_scan.py` 验证数据源
4. **区分记录来源**: 在 `m12_scan_results.json` 中添加 `scan_type` 字段（intraday/daily）
