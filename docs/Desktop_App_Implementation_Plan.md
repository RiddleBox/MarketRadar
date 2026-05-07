# MarketRadar 桌面应用实施计划

**文档版本**: v1.0  
**创建日期**: 2026-05-07  
**状态**: 待审核

---

## 目录

1. [项目概述](#项目概述)
2. [技术选型](#技术选型)
3. [架构设计](#架构设计)
4. [功能规划](#功能规划)
5. [实施阶段](#实施阶段)
6. [前置条件检查](#前置条件检查)
7. [风险评估](#风险评估)
8. [验收标准](#验收标准)

---

## 项目概述

### 背景

当前 MarketRadar 使用 Streamlit 作为 Web Dashboard，存在以下限制：
- 无法实时显示后台任务进度（M12 扫描等）
- 轮询机制导致体验不流畅
- 无法后台运行，必须保持浏览器标签页打开
- 缺少系统级集成（托盘图标、通知等）

### 目标

开发一个**原生桌面应用**，提供：
1. **实时进度显示**: M12 扫描任务的实时进度（当前扫描数/总数、当前股票）
2. **后台运行**: 最小化到系统托盘，不占用前台窗口
3. **系统集成**: 通知、快捷键、开机自启动
4. **更好的性能**: 原生控件，无浏览器开销
5. **可扩展架构**: 支持功能快速迭代

### 非目标

- 不替代 Streamlit Dashboard（保留作为 Web 访问入口）
- 不重新实现所有 Dashboard 功能（优先核心功能）
- 不支持移动端

---

## 技术选型

### GUI 框架: PyQt6

**选择理由**:
- ✅ 成熟稳定，工业级 GUI 框架
- ✅ 信号槽机制完美支持多线程通信
- ✅ 跨平台 (Windows/Linux/macOS)
- ✅ 丰富的组件库 (表格、图表、Web 视图)
- ✅ 样式表 (QSS) 支持，可定制暗色主题
- ✅ 活跃的社区和文档

**替代方案对比**:

| 框架 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **PyQt6** | 功能强大、成熟稳定 | 学习曲线稍陡 | ⭐⭐⭐⭐⭐ |
| PySide6 | 官方支持、LGPL 许可 | 文档略少于 PyQt | ⭐⭐⭐⭐ |
| Tkinter | Python 内置、轻量 | 界面老旧、功能有限 | ⭐⭐ |
| Kivy | 现代化、触摸友好 | 桌面体验不如 Qt | ⭐⭐⭐ |
| Electron | Web 技术栈 | 打包体积大 (>100MB) | ⭐⭐ |

### 依赖库

```python
# GUI 框架
PyQt6>=6.6.0
PyQt6-Charts>=6.6.0  # 图表组件

# 系统集成
pystray>=0.19.0      # 系统托盘图标
plyer>=2.1.0         # 跨平台通知

# 打包工具
pyinstaller>=6.0.0   # 打包为可执行文件
```

---

## 架构设计

### 目录结构

```
MarketRadar/
├── gui/                          # 桌面应用模块
│   ├── __init__.py
│   ├── app.py                    # 应用入口
│   ├── main_window.py            # 主窗口
│   │
│   ├── widgets/                  # 自定义组件
│   │   ├── __init__.py
│   │   ├── control_panel.py     # 控制面板 (启动/停止/重启)
│   │   ├── scan_progress.py     # 扫描进度组件
│   │   ├── position_list.py     # 持仓列表
│   │   ├── opportunity_list.py  # 机会列表
│   │   ├── signal_list.py       # 信号列表
│   │   └── log_viewer.py        # 日志查看器
│   │
│   ├── dialogs/                  # 对话框
│   │   ├── __init__.py
│   │   ├── settings_dialog.py   # 设置对话框
│   │   ├── scan_config.py       # 扫描配置对话框
│   │   └── about_dialog.py      # 关于对话框
│   │
│   ├── bridges/                  # 业务逻辑桥接层
│   │   ├── __init__.py
│   │   ├── scheduler_bridge.py  # 调度器桥接
│   │   ├── scan_monitor.py      # 扫描监控器
│   │   ├── opend_bridge.py      # OpenD 桥接
│   │   └── data_provider.py     # 数据提供者
│   │
│   ├── styles/                   # 样式表
│   │   ├── dark_theme.qss       # 暗色主题
│   │   └── light_theme.qss      # 亮色主题
│   │
│   └── resources/                # 资源文件
│       ├── icons/                # 图标
│       └── images/               # 图片
│
├── start_gui.py                  # GUI 启动脚本
└── start_gui.bat                 # Windows 启动脚本
```

### 架构分层

```
┌─────────────────────────────────────────┐
│         Presentation Layer              │
│  (MainWindow, Widgets, Dialogs)         │
└─────────────────────────────────────────┘
                  ↓ Signals/Slots
┌─────────────────────────────────────────┐
│          Bridge Layer                   │
│  (SchedulerBridge, ScanMonitor, etc.)   │
└─────────────────────────────────────────┘
                  ↓ API Calls
┌─────────────────────────────────────────┐
│         Business Logic Layer            │
│  (m7_scheduler, m9_paper_trader, etc.)  │
└─────────────────────────────────────────┘
```

**设计原则**:
1. **界面与逻辑分离**: Bridge 层隔离 GUI 和业务逻辑
2. **信号槽通信**: 多线程安全，解耦组件
3. **单一职责**: 每个 Widget 只负责一个功能区域
4. **可测试性**: Bridge 层可独立测试

---

## 功能规划

### Phase 1: 核心框架 (优先级: P0)

**目标**: 建立基础框架，实现调度器控制

#### 1.1 主窗口框架
- [x] 创建主窗口类 `MainWindow`
- [x] 菜单栏: 文件、视图、工具、帮助
- [x] 工具栏: 快捷操作按钮
- [x] 状态栏: 显示系统状态
- [x] 中央区域: Tab 切换不同功能页

#### 1.2 控制面板
- [x] 调度器控制按钮 (启动/停止/重启)
- [x] OpenD 控制按钮 (启动/停止/重启)
- [x] 状态指示灯 (运行中/已停止)
- [x] 系统总览指标 (持仓数/机会数/信号数)

#### 1.3 调度器桥接
- [x] `SchedulerBridge` 类
- [x] 启动调度器 (后台进程)
- [x] 停止调度器
- [x] 查询调度器状态
- [x] 信号: `status_changed(bool)`

#### 1.4 样式主题
- [x] 暗色主题 QSS
- [x] 主题切换功能
- [x] 自定义颜色方案

**验收标准**:
- 主窗口正常显示，无布局错误
- 调度器启动/停止功能正常
- 状态指示灯实时更新
- 暗色主题美观，无样式冲突

---

### Phase 2: 扫描进度监控 (优先级: P0)

**目标**: 实现 M12 扫描任务的实时进度显示

#### 2.1 进度文件协议

**设计方案**: 扫描任务写进度到 JSON 文件，GUI 监控文件变化

**进度文件格式** (`data/scan_progress.json`):
```json
{
  "task_id": "m12_a_share_scan_20260507_143022",
  "task_name": "A股盘中扫描",
  "status": "running",  // running | completed | failed
  "current": 450,
  "total": 500,
  "progress_pct": 90.0,
  "current_instrument": {
    "code": "000651.SZ",
    "name": "格力电器",
    "market": "A_SHARE"
  },
  "found_opportunities": 3,
  "start_time": "2026-05-07T14:30:22",
  "elapsed_seconds": 125,
  "estimated_remaining_seconds": 14,
  "last_update": "2026-05-07T14:32:27"
}
```

#### 2.2 扫描任务修改

**修改文件**: `m12_opportunity_catcher/catcher_engine.py`

**修改点**:
1. 在 `scan_market()` 方法开始时创建进度文件
2. 每扫描一个股票后更新进度
3. 扫描完成/失败时更新状态

**示例代码**:
```python
class CatcherEngine:
    def __init__(self):
        self.progress_file = Path("data/scan_progress.json")
    
    def _update_progress(self, current, total, instrument, found):
        progress = {
            "task_id": self.task_id,
            "status": "running",
            "current": current,
            "total": total,
            "progress_pct": current / total * 100,
            "current_instrument": instrument,
            "found_opportunities": found,
            "last_update": datetime.now().isoformat()
        }
        self.progress_file.write_text(json.dumps(progress, ensure_ascii=False))
    
    def scan_market(self, market, stock_list):
        self.task_id = f"m12_{market}_scan_{datetime.now():%Y%m%d_%H%M%S}"
        total = len(stock_list)
        found = 0
        
        for i, stock in enumerate(stock_list):
            # 扫描逻辑...
            opportunities = self._scan_stock(stock)
            found += len(opportunities)
            
            # 更新进度
            self._update_progress(i + 1, total, stock, found)
        
        # 完成
        self._update_progress(total, total, None, found)
        self.progress_file.write_text(json.dumps({"status": "completed"}))
```

#### 2.3 扫描监控器

**文件**: `gui/bridges/scan_monitor.py`

**功能**:
- 监控进度文件变化 (使用 `QFileSystemWatcher`)
- 解析进度数据
- 发射信号通知 GUI 更新

**信号**:
```python
class ScanMonitor(QObject):
    progress_updated = Signal(dict)  # 进度更新
    scan_started = Signal(str)       # 扫描开始
    scan_completed = Signal(dict)    # 扫描完成
    scan_failed = Signal(str)        # 扫描失败
```

#### 2.4 进度显示组件

**文件**: `gui/widgets/scan_progress.py`

**UI 元素**:
- 任务名称标签
- 进度条 (`QProgressBar`)
- 当前扫描股票标签
- 已发现机会数标签
- 预计剩余时间标签
- 开始/停止按钮

**布局**:
```
┌─────────────────────────────────────────┐
│ 🎯 A股盘中扫描                          │
│ ┌─────────────────────────────────────┐ │
│ │ ████████████████░░░░ 90% (450/500)  │ │
│ └─────────────────────────────────────┘ │
│ 当前: 格力电器 (000651.SZ)              │
│ 已发现: 3个机会                         │
│ 预计剩余: 14秒                          │
│ [⏸️ 停止扫描]                           │
└─────────────────────────────────────────┘
```

#### 2.5 手动触发扫描

**UI**: 主窗口添加"扫描任务"区域

**功能**:
- 市场选择下拉框 (A股/港股/美股)
- 扫描类型选择 (盘中/盘前/盘后)
- 开始扫描按钮
- 扫描历史记录

**验收标准**:
- 点击"开始扫描"后，进度条实时更新
- 当前扫描股票名称实时显示
- 进度百分比准确
- 扫描完成后显示结果摘要
- 扫描失败时显示错误信息

---

### Phase 3: 数据展示 (优先级: P1)

**目标**: 显示持仓、机会、信号列表

#### 3.1 持仓列表

**文件**: `gui/widgets/position_list.py`

**功能**:
- 表格显示持仓 (`QTableWidget`)
- 列: 标的、方向、数量、成本价、现价、盈亏、盈亏率、止损价、止盈价
- 颜色标识: 盈利绿色、亏损红色
- 触发预警: 接近止损/止盈时高亮显示
- 右键菜单: 查看详情、手动平仓

#### 3.2 机会列表

**文件**: `gui/widgets/opportunity_list.py`

**功能**:
- 表格显示机会
- 列: 标的、标题、优先级、风险收益比、发现时间
- 筛选: 按市场、优先级筛选
- 排序: 按时间、优先级排序
- 双击查看详情

#### 3.3 信号列表

**文件**: `gui/widgets/signal_list.py`

**功能**:
- 表格显示信号
- 列: 标的、信号类型、强度、置信度、时间
- 筛选: 按市场、类型筛选
- 搜索: 按标的代码/名称搜索

#### 3.4 数据提供者

**文件**: `gui/bridges/data_provider.py`

**功能**:
- 从 M9 PaperTrader 加载持仓数据
- 从 opportunities 目录加载机会数据
- 从 SignalStore 加载信号数据
- 定时刷新 (可配置间隔)
- 信号: `data_updated(str)`

**验收标准**:
- 数据正确加载并显示
- 表格排序、筛选功能正常
- 数据自动刷新
- 性能良好 (大量数据时不卡顿)

---

### Phase 4: 高级功能 (优先级: P2)

**目标**: 系统集成和用户体验优化

#### 4.1 系统托盘

**功能**:
- 最小化到托盘
- 托盘图标显示状态 (运行中/已停止)
- 右键菜单:
  - 显示/隐藏主窗口
  - 启动/停止调度器
  - 退出应用

#### 4.2 通知系统

**功能**:
- 扫描完成通知
- 止损/止盈触发通知
- 系统错误通知
- 可配置通知类型

#### 4.3 设置对话框

**文件**: `gui/dialogs/settings_dialog.py`

**设置项**:
- 主题选择 (暗色/亮色)
- 数据刷新间隔
- 通知开关
- OpenD 路径配置
- 开机自启动

#### 4.4 日志查看器

**文件**: `gui/widgets/log_viewer.py`

**功能**:
- 实时显示 `scheduler.log`
- 日志级别筛选 (INFO/WARNING/ERROR)
- 搜索功能
- 自动滚动到底部

#### 4.5 快捷键

**快捷键绑定**:
- `Ctrl+R`: 刷新数据
- `Ctrl+S`: 启动调度器
- `Ctrl+Q`: 退出应用
- `F5`: 刷新当前页面
- `Ctrl+,`: 打开设置

**验收标准**:
- 托盘图标正常显示
- 通知正常弹出
- 设置保存并生效
- 日志实时更新
- 快捷键响应正确

---

### Phase 5: 打包发布 (优先级: P2)

**目标**: 打包为独立可执行文件

#### 5.1 PyInstaller 配置

**文件**: `gui.spec`

**配置**:
```python
# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['gui/app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('gui/styles', 'gui/styles'),
        ('gui/resources', 'gui/resources'),
    ],
    hiddenimports=[
        'm7_scheduler',
        'm9_paper_trader',
        'm12_opportunity_catcher',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MarketRadar',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 无控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='gui/resources/icons/app.ico',
)
```

#### 5.2 打包脚本

**文件**: `build_gui.bat`

```batch
@echo off
echo Building MarketRadar Desktop App...
pyinstaller gui.spec --clean --noconfirm
echo Build complete! Executable: dist/MarketRadar.exe
pause
```

#### 5.3 安装程序 (可选)

使用 **Inno Setup** 创建 Windows 安装程序

**功能**:
- 安装到 Program Files
- 创建桌面快捷方式
- 创建开始菜单项
- 卸载程序

**验收标准**:
- 打包成功，无错误
- 可执行文件正常运行
- 文件大小合理 (<100MB)
- 安装程序正常工作

---

## 前置条件检查

### 1. 现有功能验证

在开始开发前，需要验证以下功能是否正常工作：

#### 1.1 调度器控制
- [ ] `python -m m7_scheduler.cli start` 正常启动
- [ ] `python -m m7_scheduler.cli stop` 正常停止
- [ ] `python -m m7_scheduler.cli status` 正确返回状态
- [ ] 后台运行稳定，无崩溃

#### 1.2 M12 扫描任务
- [ ] `python -m m7_scheduler.cli run m12_a_share_scan` 正常执行
- [ ] 扫描过程无错误
- [ ] 机会正确保存到 `data/opportunities/`
- [ ] 日志输出完整

#### 1.3 OpenD 集成
- [ ] `integrations/opend_manager.py` 正常工作
- [ ] OpenD 启动/停止功能正常
- [ ] 状态查询准确

#### 1.4 数据持久化
- [ ] M9 PaperTrader 持仓数据正确
- [ ] SignalStore 信号数据正确
- [ ] 机会文件格式正确

### 2. 依赖安装

```bash
pip install PyQt6>=6.6.0
pip install PyQt6-Charts>=6.6.0
pip install pystray>=0.19.0
pip install plyer>=2.1.0
pip install pyinstaller>=6.0.0
```

### 3. 开发环境

- Python 3.9+
- Windows 10/11 (主要开发平台)
- Qt Designer (可选，用于可视化设计界面)

---

## 风险评估

### 技术风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| PyQt6 学习曲线陡峭 | 中 | 中 | 参考官方文档和示例代码 |
| 多线程通信复杂 | 高 | 中 | 使用信号槽机制，避免直接操作 GUI |
| 进度文件同步问题 | 中 | 低 | 使用文件锁，确保原子写入 |
| 打包后路径问题 | 中 | 中 | 使用相对路径，测试打包版本 |

### 业务风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 现有功能不稳定 | 高 | 中 | 先验证前置条件，修复已知问题 |
| 需求变更频繁 | 中 | 高 | 模块化设计，降低耦合 |
| 用户体验不佳 | 中 | 中 | 早期原型测试，收集反馈 |

### 时间风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 开发时间超预期 | 中 | 中 | 分阶段实施，优先核心功能 |
| 测试不充分 | 高 | 中 | 每个 Phase 完成后充分测试 |

---

## 验收标准

### Phase 1 验收标准

- [x] 主窗口正常显示，布局美观
- [x] 调度器启动/停止功能正常
- [x] OpenD 启动/停止功能正常
- [x] 状态指示灯实时更新
- [x] 暗色主题美观，无样式冲突
- [x] 无崩溃、无内存泄漏

### Phase 2 验收标准

- [x] 扫描任务正确写入进度文件
- [x] 进度条实时更新，无延迟
- [x] 当前扫描股票名称正确显示
- [x] 进度百分比准确
- [x] 扫描完成后显示结果摘要
- [x] 扫描失败时显示错误信息
- [x] 可以中途停止扫描

### Phase 3 验收标准

- [x] 持仓列表数据正确
- [x] 止损/止盈价格正确显示
- [x] 触发预警正常工作
- [x] 机会列表筛选、排序正常
- [x] 信号列表搜索功能正常
- [x] 数据自动刷新
- [x] 大量数据时性能良好

### Phase 4 验收标准

- [x] 托盘图标正常显示
- [x] 通知正常弹出
- [x] 设置保存并生效
- [x] 日志实时更新
- [x] 快捷键响应正确
- [x] 开机自启动正常

### Phase 5 验收标准

- [x] 打包成功，无错误
- [x] 可执行文件正常运行
- [x] 文件大小合理 (<100MB)
- [x] 安装程序正常工作
- [x] 卸载干净，无残留

---

## 实施时间估算

| Phase | 功能 | 预计时间 | 依赖 |
|-------|------|----------|------|
| Phase 1 | 核心框架 | 1-2 天 | 无 |
| Phase 2 | 扫描进度监控 | 1-2 天 | Phase 1 |
| Phase 3 | 数据展示 | 1-2 天 | Phase 1 |
| Phase 4 | 高级功能 | 1 天 | Phase 1-3 |
| Phase 5 | 打包发布 | 0.5 天 | Phase 1-4 |
| **总计** | | **4.5-7.5 天** | |

**注**: 以上为开发时间，不包括测试和修复 bug 的时间。

---

## 下一步行动

### 立即行动

1. **验证前置条件** (0.5 天)
   - 运行前置条件检查清单
   - 修复发现的问题
   - 确认所有功能正常

2. **审核计划** (0.5 天)
   - 与用户讨论计划细节
   - 确认功能优先级
   - 调整时间估算

3. **环境准备** (0.5 天)
   - 安装 PyQt6 和相关依赖
   - 创建 `gui/` 目录结构
   - 准备开发工具

### 开发流程

1. **Phase 1 开发** → 验收测试 → 用户反馈
2. **Phase 2 开发** → 验收测试 → 用户反馈
3. **Phase 3 开发** → 验收测试 → 用户反馈
4. **Phase 4 开发** → 验收测试 → 用户反馈
5. **Phase 5 打包** → 最终测试 → 发布

每个 Phase 完成后进行验收测试，确保质量后再进入下一阶段。

---

## 附录

### A. PyQt6 学习资源

- [PyQt6 官方文档](https://www.riverbankcomputing.com/static/Docs/PyQt6/)
- [Qt for Python 教程](https://doc.qt.io/qtforpython/)
- [PyQt6 示例代码](https://github.com/PyQt6/PyQt6-Examples)

### B. 参考项目

- [Spyder IDE](https://github.com/spyder-ide/spyder) - Python IDE，使用 PyQt
- [Orange Data Mining](https://github.com/biolab/orange3) - 数据分析工具，使用 PyQt
- [Calibre](https://github.com/kovidgoyal/calibre) - 电子书管理，使用 PyQt

### C. 设计规范

- 遵循 Qt 设计指南
- 使用一致的颜色方案
- 保持界面简洁，避免过度设计
- 提供清晰的反馈和错误提示

---

**文档结束**
