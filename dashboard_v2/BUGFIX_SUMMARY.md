# Dashboard V2 Bug 修复总结

**修复日期**: 2026-05-06  
**修复版本**: v2.0.1

---

## 已修复的问题

### ✅ 问题1：调度器启动失败

**问题**: Home 页面点击"启动调度器"后，状态仍显示未启动

**根本原因**: 
- `status()` 方法只检查 `self._thread` 是否存活
- 前台模式下 `_thread` 为 `None`，导致状态始终为 `False`

**修复方案**:
- 添加 `_is_running` 标志跟踪运行状态
- 在 `start()` 中设置为 `True`，在 `stop()` 中设置为 `False`
- 启动后立即保存状态文件

**影响文件**: `m7_scheduler/scheduler.py`

---

### ✅ 问题2：Unicode 编码错误

**问题**: 手动触发任务时报错 `UnicodeEncodeError: 'gbk' codec can't encode character '▶'`

**根本原因**: Windows 控制台默认使用 GBK 编码，Rich 库输出的 Unicode 字符无法编码

**修复方案**:
- 配置 Rich Console: `Console(force_terminal=True, legacy_windows=False)`
- 将特殊字符替换为 ASCII 安全字符（`▶` → `>`）

**影响文件**: `m7_scheduler/cli.py`

---

### ✅ 问题3：持仓页面 KeyError

**问题**: 持仓页面报错 `KeyError: 'cost_basis'`

**根本原因**: 
- Position 类使用 `entry_price` 字段
- Dashboard 代码使用 `cost_basis` 字段
- 字段名不匹配导致 KeyError

**修复方案**:
- 统一使用 `entry_price` 替代 `cost_basis`
- 统一使用 `instrument` 替代 `symbol`
- 统一使用 `entry_time` 替代 `opened_at`

**影响文件**: `dashboard_v2/pages/1_💼_持仓.py`

---

### ✅ 问题4：情绪面页面采集后没数据

**问题**: 点击"立即采集"后，采集成功但页面仍显示"暂无情绪数据"

**根本原因**:
- `SentimentEngine._save_snapshot()` 只保存 JSON 文件
- 没有调用 `SentimentStore.save()` 写入数据库
- Dashboard 从数据库读取数据

**修复方案**:
1. 在 `_save_snapshot()` 中添加数据库保存逻辑
2. 修复 SQLite UTF-8 编码问题（所有连接添加 `conn.text_factory = str`）

**影响文件**: 
- `m10_sentiment/sentiment_engine.py`
- `m10_sentiment/sentiment_store.py`

---

### ✅ 问题5：所有页面的 subprocess 调用

**问题**: 使用 `python` 命令可能调用错误的解释器

**修复方案**: 统一替换为 `sys.executable`

**影响文件**:
- `dashboard_v2/Home.py`
- `dashboard_v2/pages/4_🧠_情绪面.py`
- `dashboard_v2/pages/5_⚙️_调度器.py`

---

### ✅ 问题6：缺少 plotly 依赖

**问题**: 情绪面页面报错 `ModuleNotFoundError: No module named 'plotly'`

**修复方案**: `pip install plotly`

---

## 待处理的问题

### ⏳ 问题2：手动触发任务显示进度

**需求**: 执行 M12 扫描时显示进度（总共多少、扫了多少、还剩多少）

**当前状态**: 只显示"正在执行"，无进度信息

**建议方案**:
1. 使用 Streamlit 的 `st.progress()` 组件
2. M12 扫描任务输出进度信息到临时文件
3. Dashboard 轮询读取进度文件并更新进度条

---

## 测试验证

### 调度器启动
```bash
# 在 Dashboard Home 页面点击"启动调度器"
# 等待5秒后刷新
# ✅ 状态显示"🟢 运行中"
```

### 持仓页面
```bash
# 访问持仓页面
# ✅ 正常显示持仓列表（如果有持仓）
# ✅ 无 KeyError
```

### 情绪面页面
```bash
# 点击"立即采集"
# 等待1分钟
# ✅ 页面自动刷新并显示情绪数据
# ✅ 恐贪指数、市场情绪、方向、强度正常显示
```

---

## 文件变更清单

```
修改的文件:
- m7_scheduler/scheduler.py (调度器状态跟踪)
- m7_scheduler/cli.py (Unicode 编码修复)
- m10_sentiment/sentiment_engine.py (添加数据库保存)
- m10_sentiment/sentiment_store.py (UTF-8 编码修复)
- dashboard_v2/Home.py (subprocess 修复)
- dashboard_v2/pages/1_💼_持仓.py (字段名修复)
- dashboard_v2/pages/4_🧠_情绪面.py (subprocess 修复)
- dashboard_v2/pages/5_⚙️_调度器.py (subprocess 修复)

新增的文件:
- dashboard_v2/DESIGN.md (设计文档)
- dashboard_v2/BUGFIX_2026-05-06.md (修复报告)
- dashboard_v2/BUGFIX_ISSUE1.md (问题1详细文档)
- dashboard_v2/BUGFIX_ISSUE3.md (问题3详细文档)
- dashboard_v2/BUGFIX_ISSUE4.md (问题4详细文档)
```

---

## 下一步建议

1. **测试所有修复**: 在 Dashboard 上逐个测试修复的功能
2. **实现进度显示**: 为 M12 扫描添加进度条
3. **添加单元测试**: 为关键功能添加自动化测试
4. **性能优化**: 添加数据缓存，减少重复查询
5. **文档完善**: 更新用户手册和开发文档

---

**修复人员**: MarketRadar Team  
**审核状态**: ✅ 已完成
