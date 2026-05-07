# 问题1修复：调度器启动失败

## 问题描述
Home 页面点击"启动调度器"后，提示等待3-5秒刷新，但刷新后调度器仍显示未启动。

## 根本原因
1. 调度器在后台模式启动时，会创建子进程运行前台模式
2. 前台模式下 `scheduler.start(background=False)` 不创建线程，直接运行 `_loop()`
3. `status()` 方法只检查 `self._thread` 是否存活，导致前台模式下始终返回 `running: False`
4. 状态文件在启动时立即保存，但那时状态还未正确设置

## 修复方案

### 1. 添加 `_is_running` 标志
```python
def __init__(self, tick_interval_seconds: int = 30):
    ...
    self._is_running = False  # 标记调度器是否在运行（包括前台模式）
```

### 2. 在 `start()` 中设置标志
```python
def start(self, background: bool = True):
    ...
    self._is_running = True
    ...
```

### 3. 在 `stop()` 中清除标志
```python
def stop(self):
    self._stop_event.set()
    self._is_running = False
    ...
```

### 4. 修改 `status()` 使用新标志
```python
def status(self) -> dict:
    return {
        "running": self._is_running and not self._stop_event.is_set(),
        ...
    }
```

### 5. 启动后立即保存状态
```python
def start(self, background: bool = True):
    ...
    # 立即保存初始状态
    self._save_state()
    ...
```

## 验证结果
```bash
$ python -m m7_scheduler.cli start --background
# 等待3秒
$ cat data/scheduler_state.json | python -c "import sys, json; d=json.load(sys.stdin); print(f\"Running: {d['running']}\")"
Running: True  ✅
```

## 影响文件
- `m7_scheduler/scheduler.py`

## 测试步骤
1. 在 Dashboard Home 页面点击"🚀 启动调度器"
2. 等待3-5秒后刷新页面
3. 确认调度器状态显示为"🟢 运行中"

---

**修复时间**: 2026-05-06 22:01
**状态**: ✅ 已验证
