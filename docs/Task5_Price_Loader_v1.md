# Task 5：最小价格载入层 v1

## 1. 目标

在 Task 4 已经完成最小回测/模拟执行器后，下一步优先解决“真实数据入口”问题。

本阶段先不直接接 akshare / baostock，而是先建立一个最小 price loader，优先从本地 CSV 按 `market_config.yaml` 约定加载价格序列。

---

## 2. 当前实现

文件：`data/price_loader.py`

类：`PriceLoader`

当前能力：
- 读取 `config/market_config.yaml`
- 解析 `data_sources.csv_local`
- 按 `default_directory + filename_pattern` 定位 CSV
- 返回 `close` 序列

---

## 3. 当前支持的数据源顺序

当前仅实现：
1. `csv_local`

后续预留：
2. `akshare`
3. `baostock`

也就是说，这一步的重点是把“价格数据入口”标准化，而不是一次接满全部数据源。

---

## 4. 当前配套样例数据

已新增：
- `data/csv_cache/沪深300ETF_daily.csv`
- `data/csv_cache/上证50ETF_daily.csv`

用于验证本地价格加载与最小回测链路。

---

## 5. 下一步建议

后续增强顺序建议：
1. 让回测执行器优先调用 `PriceLoader`
2. 增加多标的自动回测
3. 再逐步补 `akshare` / `baostock`
4. 最后再考虑缓存刷新与统一数据清洗
