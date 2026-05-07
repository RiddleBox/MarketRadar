# Dashboard V2 设计文档

## 概述

Dashboard V2 是 MarketRadar 的可视化前端，采用 Streamlit 多页面架构，提供实时市场监控、持仓管理、机会发现、信号分析和调度器控制功能。

**创建时间**: 2026-05-06  
**版本**: 2.0.0  
**技术栈**: Streamlit, Plotly, Pandas

---

## 架构设计

### 目录结构

```
dashboard_v2/
├── Home.py                    # 主入口页面
├── pages/                     # 多页面目录
│   ├── 1_💼_持仓.py           # 持仓管理
│   ├── 2_🎯_机会.py           # 机会发现
│   ├── 3_🔍_信号剖面.py       # 信号决策链分析
│   ├── 4_🧠_情绪面.py         # 市场情绪监控
│   └── 5_⚙️_调度器.py         # 调度器管理
├── utils/                     # 工具模块
│   ├── __init__.py
│   └── data_loader.py         # 数据加载层
└── components/                # UI组件库
    ├── __init__.py
    └── metrics.py             # 可复用组件
```

### 设计原则

1. **模块化**: 每个页面独立，避免单文件过大（旧版1700+行）
2. **可复用**: 通用组件和数据加载逻辑抽离到独立模块
3. **容错性**: 数据文件缺失时优雅降级，不崩溃
4. **高信息密度**: 在有限空间内展示最关键信息
5. **交互性**: 支持筛选、排序、手动触发等操作

---

## 核心功能

### 1. Home 页面 (主入口)

**文件**: `Home.py`

**功能**:
- 系统总览：总资产、日盈亏、持仓数、待处理机会
- 快速导航：跳转到各子页面
- 最近信号预览（前5条）
- 系统状态指示器

**数据源**:
- `data/portfolio.db` (positions 表)
- `data/m12_scan_results.json` (opportunities)
- `data/signals/*.json` (signals)

**设计决策**:
- 使用4列布局展示核心指标
- 信号预览限制5条，避免信息过载
- 使用 emoji 增强视觉识别度

---

### 2. 持仓页面 (1_💼_持仓.py)

**优先级**: 最高 (P0)

**功能**:
- **持仓总览**: 总成本、当前市值、总盈亏、盈亏率
- **持仓列表**: 表格展示所有持仓，包含实时价格、盈亏
- **持仓详情**: 可展开查看单个持仓的详细信息
- **历史持仓**: 已平仓记录，包含胜率统计

**数据源**:
- `data/portfolio.db` (positions 表)
- `status = 'open'` 为当前持仓
- `status = 'closed'` 为历史持仓

**关键指标**:
- 成本价 (cost_basis)
- 现价 (current_price)
- 数量 (quantity)
- 盈亏 = (现价 - 成本价) × 数量
- 盈亏率 = 盈亏 / 成本 × 100%

**设计决策**:
- 使用 DataFrame 展示表格，支持排序
- 盈亏用颜色区分（绿色=盈利，红色=亏损）
- 历史持仓默认折叠，减少干扰
- 预留操作按钮（查看K线、平仓等），待后续实现

**未来迭代**:
- [ ] 集成实时行情API，自动更新 current_price
- [ ] 添加持仓分布饼图（按行业/市场）
- [ ] 添加持仓时间线图
- [ ] 实现平仓功能（调用 M5 模块）

---

### 3. 机会页面 (2_🎯_机会.py)

**优先级**: 高 (P1)

**功能**:
- **筛选器**: 按优先级、市场、方向筛选
- **机会卡片**: 展示机会标题、论点、关键假设、反驳证据
- **排序**: 优先级 > 信号数量
- **统计**: 紧急机会数、看多/看空机会数、平均信号数

**数据源**:
- `data/m12_scan_results.json`

**机会字段**:
- `opportunity_id`: 唯一标识
- `opportunity_title`: 机会标题
- `opportunity_thesis`: 投资论点
- `why_now`: 时效性说明
- `key_assumptions`: 关键假设列表
- `counter_evidence`: 反驳证据列表
- `priority_level`: urgent/position/research/watch
- `trade_direction`: BULLISH/BEARISH/NEUTRAL
- `target_markets`: 目标市场列表
- `target_instruments`: 相关标的列表
- `related_signals`: 关联信号ID列表

**设计决策**:
- 默认展开 urgent 和 position 级别机会
- 使用 badge 组件标识优先级和方向
- 关键假设和反驳证据限制显示数量（3条/2条）
- 预留"查看详情"、"查看信号"、"开仓"按钮

**未来迭代**:
- [ ] 实现机会详情页（跳转到独立页面）
- [ ] 关联信号点击跳转到信号剖面页
- [ ] 开仓功能（调用 M4 策略模块）
- [ ] 机会状态跟踪（已开仓/已失效/持续观察）

---

### 4. 信号剖面页面 (3_🔍_信号剖面.py)

**优先级**: 高 (P1)

**功能**:
- **信号选择器**: 下拉选择最近7天的信号
- **信号源展示**: 原文内容、类型、来源、时间、方向
- **影响标的**: 展示相关股票/品种
- **决策链路图**: 可视化 M0→M1→M2→M10→M3→M4 流程
- **模块详情**: 可展开查看每个模块的分析结果
  - M1 解码: 信号类型、时间范围、置信度、影响范围
  - M10 情绪: 恐贪指数、市场情绪、贡献度
  - M3 判断: 质量评分、优先级、可信度、时效性
  - M4 策略: 策略类型、参数、建议仓位
- **后续行动**: 针对每个标的的操作建议

**数据源**:
- `data/signals/*.json` (信号原始数据)
- `data/decisions/*.json` (决策记录，如果有)

**设计决策**:
- 使用 expander 组件展示决策链路，避免信息过载
- 默认展开 M1 解码模块，其他模块折叠
- 使用进度条展示置信度、质量评分等指标
- 颜色编码：绿色=正面，红色=负面，灰色=中性
- 提供原始数据查看（调试用）

**未来迭代**:
- [ ] 添加决策链路流程图（使用 Graphviz 或 Mermaid）
- [ ] 支持信号对比（选择多个信号并排展示）
- [ ] 添加信号回测结果（如果已执行）
- [ ] 集成 M3/M4 模块的实时分析（当前是读取历史数据）

---

### 5. 情绪面页面 (4_🧠_情绪面.py)

**优先级**: 中 (P2)

**功能**:
- **立即采集**: 手动触发情绪采集任务
- **当前情绪**: 恐贪指数、市场情绪标签、方向、强度
- **恐贪指数仪表盘**: Gauge 图展示 0-100 指数
- **情绪趋势**: 历史恐贪指数折线图（最近48条）
- **北向资金流向**: 净流入、沪股通、深股通
- **板块情绪**: 各板块情绪值柱状图
- **统计信息**: 平均恐贪指数、看多/看空占比

**数据源**:
- `data/sentiment/*.json` (M10 情绪模块输出)

**情绪字段**:
- `fear_greed_index`: 恐贪指数 (0-100)
- `sentiment_label`: 情绪标签（极度恐惧/恐惧/中性/贪婪/极度贪婪）
- `direction`: BULLISH/BEARISH/NEUTRAL
- `intensity`: 强度 (0-10)
- `northbound_flow`: 北向资金 {net_inflow, shanghai, shenzhen}
- `sector_sentiment`: 板块情绪 {板块名: 情绪值}

**设计决策**:
- 使用 Plotly Gauge 图展示恐贪指数，直观易读
- 趋势图添加参考线（25=恐惧，50=中性，75=贪婪）
- 板块情绪使用颜色渐变（红→黄→绿）
- 支持手动触发采集，超时60秒

**未来迭代**:
- [ ] 添加情绪预警（指数突破阈值时通知）
- [ ] 集成更多情绪指标（VIX、融资融券、换手率）
- [ ] 情绪与持仓关联分析（持仓标的的情绪分布）
- [ ] 历史情绪回测（情绪极值时的后续走势）

---

### 6. 调度器页面 (5_⚙️_调度器.py)

**优先级**: 中 (P2)

**功能**:
- **调度器状态**: 运行/停止、已启用任务数、总运行次数、总错误次数
- **任务列表**: 表格展示所有任务及其状态
- **任务详情**: 选择任务查看详细信息和统计
- **手动触发**: 点击按钮立即执行指定任务
- **最近运行记录**: 展示最近20条执行记录
- **日志查看**: 实时查看调度器日志（最近50-200行）

**数据源**:
- `data/scheduler_state.json` (调度器状态)
- `data/logs/scheduler.log` (日志文件)

**任务字段**:
- `task_name`: 任务名称
- `description`: 任务描述
- `interval_minutes`: 执行间隔（分钟）
- `time_window`: 时间窗口（如 "09:30-15:00"）
- `enabled`: 是否启用
- `run_count`: 运行次数
- `error_count`: 错误次数
- `last_run`: 上次运行时间
- `last_status`: 上次运行结果（ok/error）

**设计决策**:
- 使用表格展示任务列表，支持排序
- 手动触发任务超时5分钟，防止长时间阻塞
- 日志查看支持调整显示行数（10-200行）
- 运行记录使用 expander 展示，节省空间
- 成功率计算：(运行次数 - 错误次数) / 运行次数

**未来迭代**:
- [ ] 添加任务启用/禁用开关（直接在页面操作）
- [ ] 支持修改任务参数（间隔、时间窗口）
- [ ] 添加任务执行时间预测（下次执行时间倒计时）
- [ ] 日志搜索和过滤功能
- [ ] 任务执行历史图表（成功率趋势）

---

## 数据加载层 (utils/data_loader.py)

### 设计目标

- **统一接口**: 所有页面通过统一函数加载数据
- **容错处理**: 文件不存在时返回空数据，不抛异常
- **性能优化**: 避免重复读取，支持缓存（未来）

### 核心函数

```python
# 持仓相关
load_positions_open() -> List[Dict]
load_positions_closed() -> List[Dict]

# 机会相关
load_opportunities() -> List[Dict]

# 信号相关
load_signals_recent(days=7) -> List[Dict]
load_signal_by_id(signal_id) -> Dict

# 情绪相关
load_sentiment_latest() -> Dict
load_sentiment_history(n=48) -> List[Dict]
load_sentiment_trend(n=20) -> Dict

# 调度器相关
load_scheduler_state() -> Dict
```

### 设计决策

- 使用 `try-except` 包裹所有文件读取操作
- JSON 解析失败时返回空数据结构
- SQLite 查询使用参数化，防止注入
- 时间范围查询使用 ISO 格式字符串

### 未来迭代

- [ ] 添加数据缓存（使用 `@st.cache_data` 装饰器）
- [ ] 支持数据分页加载（大数据量时）
- [ ] 添加数据验证（schema validation）
- [ ] 支持多数据源（数据库/文件/API）

---

## UI组件库 (components/metrics.py)

### 设计目标

- **一致性**: 统一的视觉风格和交互模式
- **可复用**: 避免重复代码
- **可配置**: 支持参数自定义

### 核心组件

```python
# 指标卡片
metric_card(title, value, delta=None, color="blue")

# 盈亏徽章
profit_badge(value, show_value=True)

# 趋势指示器
trend_indicator(direction)  # up/down/neutral

# 优先级徽章
priority_badge(level)  # urgent/position/research/watch

# 信号方向徽章
signal_direction_badge(direction)  # BULLISH/BEARISH/NEUTRAL

# 状态徽章
status_badge(status)  # ok/error/running/stopped

# 空状态占位
empty_state(message, icon)
```

### 设计决策

- 使用 HTML + CSS 实现自定义样式
- 颜色方案：
  - 绿色 (#00c851): 正面、盈利、看多
  - 红色 (#ff4b4b): 负面、亏损、看空
  - 灰色 (#aaaaaa): 中性、未知
  - 蓝色 (#33b5e5): 信息、强调
  - 黄色 (#ffbb33): 警告、中等优先级
- 使用 emoji 增强视觉识别
- 支持 `unsafe_allow_html=True` 渲染

### 未来迭代

- [ ] 添加更多图表组件（K线图、热力图）
- [ ] 支持主题切换（亮色/暗色）
- [ ] 添加动画效果（数字滚动、进度条）
- [ ] 组件文档和示例

---

## 启动和部署

### 本地开发

```bash
# 启动 Dashboard V2
streamlit run dashboard_v2/Home.py --server.port 8501

# 后台运行
nohup streamlit run dashboard_v2/Home.py --server.port 8501 > dashboard.log 2>&1 &
```

### 配置文件

创建 `dashboard_v2/.streamlit/config.toml`:

```toml
[server]
port = 8501
headless = true
enableCORS = false

[theme]
primaryColor = "#33b5e5"
backgroundColor = "#0e1117"
secondaryBackgroundColor = "#1e1e2e"
textColor = "#fafafa"
font = "sans serif"
```

### 依赖管理

```bash
# 安装依赖
pip install streamlit plotly pandas

# 生成 requirements.txt
pip freeze | grep -E "streamlit|plotly|pandas" > dashboard_v2/requirements.txt
```

---

## 性能优化

### 当前状态

- 数据加载：每次页面刷新重新读取文件
- 图表渲染：Plotly 客户端渲染
- 页面大小：10-12KB Python 代码

### 优化方向

1. **数据缓存**:
   ```python
   @st.cache_data(ttl=60)  # 缓存60秒
   def load_positions_open():
       ...
   ```

2. **增量更新**:
   - 使用 WebSocket 推送数据变更
   - 仅更新变化的部分，不刷新整个页面

3. **懒加载**:
   - 历史数据按需加载
   - 图表数据分页

4. **图表优化**:
   - 大数据量时使用采样
   - 使用 `scattergl` 替代 `scatter`（WebGL 加速）

---

## 测试策略

### 单元测试

```python
# tests/test_data_loader.py
def test_load_positions_open():
    positions = load_positions_open()
    assert isinstance(positions, list)
    if positions:
        assert "symbol" in positions[0]
        assert "quantity" in positions[0]
```

### 集成测试

```python
# tests/test_dashboard_pages.py
def test_home_page_loads():
    # 使用 Streamlit testing framework
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file("dashboard_v2/Home.py")
    at.run()
    assert not at.exception
```

### 手动测试清单

- [ ] 所有页面能正常加载
- [ ] 数据文件缺失时不崩溃
- [ ] 筛选器功能正常
- [ ] 手动触发任务成功
- [ ] 图表交互正常（缩放、悬停）
- [ ] 移动端显示正常

---

## 已知问题和限制

### 当前限制

1. **实时性**: 数据需要手动刷新页面或点击"立即采集"
2. **并发**: 不支持多用户同时操作（单机部署）
3. **历史数据**: 信号和情绪数据保留时间有限
4. **权限**: 无用户认证和权限控制

### 已知问题

1. **持仓页面**: `current_price` 字段可能为空（未集成实时行情）
2. **信号剖面**: 部分信号缺少 M10/M3/M4 模块数据
3. **调度器**: 手动触发任务时页面会阻塞（同步执行）
4. **情绪面**: 板块情绪数据格式不统一

---

## 未来路线图

### 短期 (1-2周)

- [ ] 集成实时行情API（持仓页面）
- [ ] 实现开仓/平仓功能（调用 M4/M5 模块）
- [ ] 添加数据缓存（提升性能）
- [ ] 完善错误处理和日志记录

### 中期 (1-2月)

- [ ] 添加用户认证和权限控制
- [ ] 实现 WebSocket 实时推送
- [ ] 添加回测功能（历史信号效果分析）
- [ ] 移动端适配优化

### 长期 (3-6月)

- [ ] 多用户支持（数据隔离）
- [ ] 自定义仪表盘（拖拽布局）
- [ ] 机器学习模型集成（预测展示）
- [ ] 云端部署（Docker + K8s）

---

## 设计决策记录 (ADR)

### ADR-001: 为什么选择 Streamlit？

**背景**: 需要快速构建可视化前端

**决策**: 使用 Streamlit 而非 Flask/Django + React

**理由**:
- 开发速度快（纯 Python，无需前后端分离）
- 内置组件丰富（图表、表格、表单）
- 适合数据科学项目
- 社区活跃，文档完善

**权衡**:
- 灵活性较低（无法完全自定义UI）
- 性能不如原生前端框架
- 不适合复杂交互场景

---

### ADR-002: 为什么采用多页面架构？

**背景**: 旧版单文件 Dashboard 1700+ 行，难以维护

**决策**: 拆分为多个独立页面

**理由**:
- 代码可维护性提升
- 页面加载速度更快（按需加载）
- 团队协作更容易（不同人负责不同页面）
- 符合 Streamlit 最佳实践

**权衡**:
- 页面间状态共享较复杂（需要 session_state）
- 导航需要额外设计

---

### ADR-003: 为什么使用 JSON 文件而非数据库？

**背景**: 信号、情绪、机会数据存储方式

**决策**: 使用 JSON 文件存储（持仓除外）

**理由**:
- 数据结构灵活（schema-less）
- 便于调试和手动修改
- 无需额外数据库服务
- 适合小规模数据（< 10MB）

**权衡**:
- 查询性能较低（需要全文件读取）
- 并发写入可能冲突
- 数据量大时需要迁移到数据库

**未来**: 当数据量 > 100MB 或并发用户 > 10 时，迁移到 PostgreSQL

---

## 贡献指南

### 添加新页面

1. 在 `dashboard_v2/pages/` 创建新文件，命名格式：`N_emoji_名称.py`
2. 使用 `st.set_page_config()` 设置页面标题和图标
3. 从 `utils.data_loader` 导入数据加载函数
4. 从 `components.metrics` 导入UI组件
5. 遵循现有页面的布局结构

### 添加新组件

1. 在 `components/metrics.py` 添加函数
2. 使用 HTML + CSS 实现样式
3. 添加参数验证和默认值
4. 在文档中添加使用示例

### 代码规范

- 使用 4 空格缩进
- 函数和变量使用 snake_case
- 类名使用 PascalCase
- 添加类型注解（Python 3.9+）
- 添加 docstring（Google 风格）

---

## 参考资料

- [Streamlit 官方文档](https://docs.streamlit.io/)
- [Plotly Python 文档](https://plotly.com/python/)
- [MarketRadar 项目文档](../PROJECT_CONTEXT.md)
- [M12 模块设计](../m12_opportunity_catcher/README.md)

---

## 变更日志

### v2.0.0 (2026-05-06)

- 初始版本发布
- 实现5个核心页面
- 添加数据加载层和UI组件库
- 完成基础功能开发

---

**文档维护者**: MarketRadar Team  
**最后更新**: 2026-05-06
