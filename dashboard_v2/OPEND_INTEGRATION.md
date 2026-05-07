# OpenD 集成功能说明

**创建日期**: 2026-05-07  
**功能版本**: Dashboard V2.1

---

## 功能概述

Dashboard V2 现已集成 FutuOpenD 进程管理功能，用户可以直接在 Dashboard 中启动、停止、监控 OpenD 进程，无需手动操作。

### 核心功能

1. **OpenD 进程管理** - 启动/停止/重启 FutuOpenD
2. **状态实时监控** - 显示 OpenD 运行状态、PID、端口
3. **智能错误提示** - M12 任务失败时显示根因和解决方案
4. **依赖关系提示** - 明确告知哪些功能依赖 OpenD

---

## 使用指南

### 1. 启动 Dashboard

```bash
streamlit run dashboard_v2/Home.py --server.port 8501
```

访问: http://localhost:8501

### 2. OpenD 管理（主页）

在主页的 **🔌 FutuOpenD 行情网关** 区域：

#### 状态显示
- **OpenD 状态**: 🟢 运行中 / 🔴 已停止
- **进程 PID**: 显示进程 ID
- **端口**: 默认 11111
- **地址**: 默认 127.0.0.1

#### 控制按钮
- **🚀 启动 OpenD**: 启动 FutuOpenD 进程（等待 5 秒确认启动成功）
- **⏸️ 停止 OpenD**: 优雅停止进程（5秒超时后强制杀死）
- **🔄 重启 OpenD**: 停止后重新启动

#### 状态提示
- ⚠️ **OpenD 未运行**: 提示 M12 市场扫描任务将无法执行
- ✅ **OpenD 运行中**: 显示可执行的市场扫描类型

### 3. 调度器管理

在 **⚙️ 调度器控制** 区域：

- **启动调度器**: 后台启动调度器进程
- **停止调度器**: 停止调度器进程
- **重启调度器**: 重启调度器

**注意**: 建议先启动 OpenD，再启动调度器，确保 M12 任务能正常执行。

### 4. 查看任务执行结果

前往 **⚙️ 调度器** 页面，查看 **最近运行记录**：

#### 成功任务
- 状态: 🟢 ok
- 显示执行结果（机会数、标的等）

#### 失败任务
- 状态: 🔴 error
- **错误信息**: 显示详细错误原因
- **错误类型**: 分类错误（如 OpenD_Connection_Failed）
- **建议**: 提供解决方案
- **解决方案**: 针对 OpenD 连接失败，提供操作步骤

---

## 典型使用场景

### 场景 1: 首次启动系统

1. 打开 Dashboard (http://localhost:8501)
2. 检查 OpenD 状态 → 🔴 已停止
3. 点击 **🚀 启动 OpenD**
4. 等待 5 秒，确认状态变为 🟢 运行中
5. 点击 **🚀 启动调度器**
6. 前往 **🎯 机会** 页面，等待 M12 扫描结果

### 场景 2: OpenD 异常退出

**症状**: 调度器页面显示 M12 任务失败，错误类型为 `OpenD_Connection_Failed`

**解决步骤**:
1. 前往主页
2. 检查 OpenD 状态 → 🔴 已停止
3. 点击 **🚀 启动 OpenD**
4. 确认状态变为 🟢 运行中
5. 返回调度器页面，手动触发失败的任务

### 场景 3: 调度器卡死

**症状**: 调度器状态显示运行中，但任务长时间未更新

**解决步骤**:
1. 前往主页
2. 点击 **🔄 重启调度器**
3. 等待 3-5 秒
4. 刷新页面，确认调度器重新启动

### 场景 4: 手动触发 M12 扫描

1. 确保 OpenD 状态为 🟢 运行中
2. 前往主页 **🎯 手动触发任务** 区域
3. 选择市场（A股/港股/美股）
4. 选择扫描类型（盘中/盘前/盘后）
5. 点击 **▶ 执行 M12 扫描**
6. 等待执行完成（最多 5 分钟）
7. 前往 **🎯 机会** 页面查看结果

---

## 错误处理

### OpenD 连接失败

**错误信息**: `FutuOpenD 连接失败：OpenD 进程未运行或端口不可达`

**原因**:
- OpenD 进程未启动
- OpenD 启动失败
- 端口被占用

**解决方案**:
1. 检查 OpenD 可执行文件路径是否正确（`config/opend_config.yaml`）
2. 检查端口 11111 是否被占用
3. 查看 OpenD 日志: `logs/opend.log`
4. 尝试重启 OpenD

### OpenD 启动失败

**错误信息**: `OpenD 启动后立即退出，请检查日志`

**原因**:
- 可执行文件路径错误
- 缺少依赖库
- 配置文件错误

**解决方案**:
1. 检查 `config/opend_config.yaml` 中的可执行文件路径
2. 确认 FutuOpenD 已正确安装
3. 查看 `logs/opend.log` 获取详细错误信息

### 调度器任务超时

**错误信息**: `执行超时（5分钟）`

**原因**:
- 网络延迟
- 数据量过大
- OpenD 响应慢

**解决方案**:
1. 检查网络连接
2. 重启 OpenD
3. 减少扫描范围（修改监控池）

---

## 配置说明

### OpenD 配置文件

路径: `config/opend_config.yaml`

```yaml
opend:
  executable:
    windows: "C:/Program Files/Futu/FutuOpenD/OpenD.exe"
    linux: "/root/futu/FutuOpenD"
    darwin: "/Applications/FutuOpenD.app/Contents/MacOS/FutuOpenD"
  
  host: "127.0.0.1"
  port: 11111
  
  startup:
    auto_start: true
    wait_seconds: 5
    check_interval: 2
    max_retries: 3
```

**重要参数**:
- `executable`: OpenD 可执行文件路径（根据操作系统选择）
- `port`: OpenD 监听端口（默认 11111）
- `wait_seconds`: 启动后等待时间（秒）

### 数据源配置

路径: `config/data_sources.yaml`

```yaml
primary:
  a_share: futu      # A股主数据源
  hk_share: futu     # 港股主数据源
  us_share: futu     # 美股主数据源

fallback:
  a_share: akshare   # A股备用数据源
  hk_share: yfinance # 港股备用数据源
  us_share: yfinance # 美股备用数据源
```

**说明**:
- `primary`: 主数据源（优先使用）
- `fallback`: 备用数据源（主数据源失败时自动降级）

---

## 技术架构

### OpenD 管理器

**模块**: `integrations/opend_manager.py`

**核心类**: `OpenDManager`

**主要方法**:
- `is_running()`: 检查进程是否运行
- `get_pid()`: 获取进程 PID
- `start(wait=True)`: 启动进程
- `stop()`: 停止进程
- `restart()`: 重启进程
- `status()`: 获取状态信息

**进程检测**:
1. 检查 PID 文件 (`logs/opend.pid`)
2. 使用 `psutil` 遍历进程列表
3. 匹配进程名包含 "opend" 或 "futu"

### 调度器错误处理

**位置**: `m7_scheduler/scheduler.py` → `_task_m12_market_scan()`

**错误分类**:
- `OpenD_Connection_Failed`: OpenD 连接失败
- `OpenD_Error`: OpenD 其他错误
- 其他: 通用错误

**错误信息结构**:
```python
{
    "error": "错误描述",
    "error_type": "错误类型",
    "market": "市场",
    "suggestion": "解决建议"
}
```

### Dashboard 集成

**主页**: `dashboard_v2/Home.py`
- OpenD 状态显示
- OpenD 控制按钮
- 依赖关系提示

**调度器页面**: `dashboard_v2/pages/5_⚙️_调度器.py`
- 任务执行记录
- 错误详情显示
- 解决方案提示

---

## 依赖关系

### M12 任务依赖 OpenD

以下任务依赖 FutuOpenD 实时行情数据：

- `m12_a_share_scan`: A股盘中扫描
- `m12_hk_scan`: 港股盘中扫描
- `m12_us_scan`: 美股盘中扫描
- `m12_premarket_*`: 盘前扫描
- `m12_postmarket_*`: 盘后扫描

**注意**: 如果 OpenD 未运行，这些任务将失败并记录错误。

### 其他任务不依赖 OpenD

以下任务可以在 OpenD 未运行时正常执行：

- `signal_pipeline`: 信号处理管道
- `price_update`: 价格更新（使用备用数据源）
- `daily_review`: 每日复盘
- `news_collect`: 新闻采集
- `sentiment_collect`: 情绪采集

---

## 常见问题

### Q1: OpenD 启动后立即退出？

**A**: 检查以下几点：
1. 可执行文件路径是否正确
2. 是否有权限执行该文件
3. 查看 `logs/opend.log` 获取详细错误

### Q2: 调度器显示运行中，但任务不执行？

**A**: 可能原因：
1. 任务时间窗口限制（非交易时段）
2. 任务间隔未到
3. 调度器进程卡死

解决方案：重启调度器

### Q3: M12 扫描一直失败？

**A**: 检查：
1. OpenD 是否运行
2. 网络连接是否正常
3. 是否在交易时段
4. 查看调度器日志获取详细错误

### Q4: 如何修改 OpenD 端口？

**A**: 修改 `config/opend_config.yaml` 中的 `port` 参数，然后重启 OpenD。

### Q5: 可以不使用 OpenD 吗？

**A**: 可以，修改 `config/data_sources.yaml`，将主数据源改为 `akshare` 或 `yfinance`。但会失去实时行情能力。

---

## 更新日志

### v2.1 (2026-05-07)

**新增功能**:
- ✅ OpenD 进程管理（启动/停止/重启）
- ✅ OpenD 状态实时监控
- ✅ M12 任务错误智能诊断
- ✅ 任务失败原因详细显示
- ✅ OpenD 连接失败解决方案提示

**改进**:
- ✅ 调度器错误处理增强
- ✅ Dashboard 用户体验优化
- ✅ 错误信息结构化

**修复**:
- ✅ 修复 None 切片漏洞（5处）
- ✅ 修复调度器状态显示问题

---

## 反馈与支持

如有问题或建议，请：
1. 查看 `logs/opend.log` 和 `logs/scheduler.log`
2. 检查 Dashboard 错误提示
3. 参考本文档的常见问题部分

---

**文档维护**: Claude  
**最后更新**: 2026-05-07
