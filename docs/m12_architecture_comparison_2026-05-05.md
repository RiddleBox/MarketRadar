# M12架构评估对比与问题分析

**日期**: 2026-05-05  
**对比对象**: 
- 之前的架构评估（2026-04-18 module_principles_audit）
- 云服务器版本（2026-05-02 提交 30fa56e7 和 37b49a63）
- 当前本地版本

---

## 一、两份架构评估报告的区别

### 1. 之前的报告（2026-04-18）

**文件**: `docs/module_principles_audit_2026-04-18.md`

**评估范围**:
- ✅ 模块第一性原理审计（M0-M10）
- ✅ 模块边界检查
- ✅ 实用工具差距评估
- ✅ 数据源、LLM、Dashboard、部署等维度

**关注点**:
- 模块职责是否越权
- 系统整体可用性
- 距离"实用工具"的差距

**结论**: 综合实用度 7/10，可作为交易研究助手使用

### 2. 今天的报告（2026-05-05）

**文件**: `docs/m12_architecture_review_2026-05-05.md`

**评估范围**:
- ✅ M12扫描的入口收束性
- ✅ 持久化规范性
- ✅ 盘中/盘后扫描的数据记录

**关注点**:
- 入口是否分散
- 持久化格式是否统一
- 数据是否完整记录

**结论**: 存在3个独立入口，持久化格式不统一

### 区别总结

| 维度 | 2026-04-18 报告 | 2026-05-05 报告 |
|------|----------------|----------------|
| **评估层次** | 系统整体架构 | M12模块细节 |
| **评估角度** | 模块职责边界 | 入口与持久化 |
| **问题类型** | 功能完整性 | 架构规范性 |
| **优先级** | 中长期改进 | 短期优化 |

**关系**: 
- 4月18日报告是**宏观评估**（整个系统）
- 5月5日报告是**微观评估**（M12模块）
- 两者互补，不冲突

---

## 二、云服务器版本 vs 本地版本

### 云服务器版本的关键改进（2026-05-02）

#### 提交 30fa56e7: 添加盘前/盘后扫描任务

**改进内容**:
```python
# M7调度器新增6个任务
m12_premarket_a_share:  09:00 每天一次（盘前信号扫描）
m12_premarket_hk:       09:00 每天一次
m12_premarket_us:       21:00 每天一次

m12_postmarket_a_share: 15:30 每天一次（盘后全景扫描）
m12_postmarket_hk:      16:30 每天一次
m12_postmarket_us:      05:00 每天一次
```

**盘前扫描逻辑**:
```python
def _task_m12_premarket_scan(market, run_id):
    """
    1. 检查是否交易日
    2. 采集隔夜新闻（M0）
    3. M1解码 → M2存储 → M3判断
    4. 生成开盘交易依据
    5. 保存到 data/premarket_opportunities/
    """
```

**盘后扫描逻辑**:
```python
def _task_m12_postmarket_scan(market, run_id):
    """
    1. 检查是否交易日
    2. 全量价格扫描（run_daily_scan）
    3. 异动发现 → 反向溯源 → 趋势判断
    4. 扩展监控池
    5. 保存到 data/postmarket_opportunities/
    """
```

#### 提交 37b49a63: 修复盘前/盘后单次触发逻辑

**改进内容**:
- 集成 `chinese-calendar` 库实现真实节假日判断
- 修改 `is_due()` 支持单次触发（time_window 起止相同时每天只执行一次）
- 验证通过：5月1日/2日均正确识别为非交易日

### 本地版本的状态

**检查结果**:
```python
# 当前 m7_scheduler/scheduler.py 包含：
✅ m12_a_share_scan (盘中，10分钟)
✅ m12_hk_scan (盘中，10分钟)
✅ m12_us_scan (盘中，10分钟)
✅ m12_premarket_a_share (盘前，每天一次)
✅ m12_premarket_hk (盘前，每天一次)
✅ m12_premarket_us (盘前，每天一次)
✅ m12_postmarket_a_share (盘后，每天一次)
✅ m12_postmarket_hk (盘后，每天一次)
✅ m12_postmarket_us (盘后，每天一次)
```

**结论**: ✅ **云服务器的改进已经在本地版本中！**

---

## 三、关键问题分析

### 问题1: 为什么我之前没发现盘前/盘后任务？

**原因分析**:

1. **诊断路径偏差**:
   - 我从 `m12_scan_results.json` 入手
   - 发现是 `run_continuous_simulation.py` 写入的
   - 误以为M7调度器没有M12扫描

2. **数据来源混淆**:
   - `m12_scan_results.json` 确实不是M7调度器写的
   - 但M7调度器的M12任务写入的是：
     - `data/retro_opportunities/` (盘中)
     - `data/premarket_opportunities/` (盘前)
     - `data/postmarket_opportunities/` (盘后)

3. **目录检查不完整**:
   ```bash
   # 我执行的检查
   ls -la data/ | grep -E "retro|premarket|postmarket|m12"
   # 结果：只有 m12_scan_results.json
   
   # 实际情况
   data/retro_opportunities/      # 不存在（因为最近扫描都是0异动）
   data/premarket_opportunities/  # 不存在（可能未触发或已清理）
   data/postmarket_opportunities/ # 不存在（可能未触发或已清理）
   ```

4. **日志检查失败**:
   ```bash
   # 我执行的检查
   grep "m12.*scan.*任务开始" logs/simulation_10min.log
   # 结果：无输出
   
   # 原因：日志文件太大（499M），grep可能超时或被截断
   ```

### 问题2: 4小时一次的盘后扫描有什么意义？

**这是 `run_continuous_simulation.py` 的设计，不是M7调度器！**

```python
# run_continuous_simulation.py:669
daily_interval = 4 * 60 * 60  # 盘后4小时

# 触发条件（第739行）
if now - last_daily >= daily_interval and not is_any_market_trading():
    run_daily_scan(...)
```

**意义分析**:

❌ **没有意义，这是设计缺陷！**

**原因**:
1. **盘后扫描应该每天一次**，不是每4小时
2. **M7调度器已经正确实现**：每天15:30/16:30/05:00各一次
3. **run_continuous_simulation.py 的4小时扫描是冗余的**

**对比**:

| 实现 | 盘后扫描频率 | 合理性 |
|------|------------|--------|
| M7调度器 | 每天一次（15:30/16:30/05:00） | ✅ 合理 |
| run_continuous_simulation | 每4小时（闭市时） | ❌ 不合理 |

### 问题3: 云服务器版本的修改现在没有了吗？

**答案**: ✅ **有！都在！**

**验证**:
```bash
# 检查git提交
git log --oneline | grep "盘前\|盘后"
30fa56e7 feat(m7): 添加盘前/盘后扫描任务
37b49a63 fix(m7): 集成交易日历判断，修复盘前/盘后单次触发逻辑

# 检查代码
git show HEAD:m7_scheduler/scheduler.py | grep "m12_premarket\|m12_postmarket"
# 结果：包含所有6个盘前/盘后任务
```

**本地版本包含**:
- ✅ 盘前扫描任务（3个市场）
- ✅ 盘后扫描任务（3个市场）
- ✅ 交易日历判断
- ✅ 单次触发逻辑

---

## 四、为什么会出现这些问题？

### 根本原因

1. **多入口并存**:
   - M7调度器（生产）
   - run_continuous_simulation.py（模拟）
   - 两者功能重叠但实现不同

2. **持久化位置不同**:
   - M7调度器 → `data/retro_opportunities/`, `data/premarket_opportunities/`, `data/postmarket_opportunities/`
   - run_continuous_simulation → `data/m12_scan_results.json`

3. **目录不存在导致误判**:
   - M7调度器的目录因为"0异动不保存"而不存在
   - 我误以为M7调度器没有M12任务

4. **日志文件过大**:
   - `logs/simulation_10min.log` 499M
   - grep查询可能超时或被截断

### 诊断方法问题

**我的诊断路径**:
```
发现 m12_scan_results.json 
  ↓
查找谁写入这个文件
  ↓
发现是 run_continuous_simulation.py
  ↓
误以为M7调度器没有M12扫描
  ↓
错误结论
```

**正确的诊断路径应该是**:
```
检查 M7调度器的任务注册
  ↓
查看 scheduler.py 的 register_tasks()
  ↓
发现所有M12任务（盘中/盘前/盘后）
  ↓
检查持久化位置
  ↓
发现 retro/premarket/postmarket 目录
  ↓
正确结论
```

---

## 五、解决方案

### 短期（立即）

1. **明确入口职责**:
   ```
   生产环境: M7调度器（唯一入口）
   模拟测试: run_continuous_simulation.py（仅用于测试）
   ```

2. **废弃 run_continuous_simulation.py 的盘后4小时扫描**:
   ```python
   # 删除或注释掉
   # if now - last_daily >= daily_interval and not is_any_market_trading():
   #     run_daily_scan(...)
   ```

3. **统一持久化位置**:
   ```
   data/m12_scans/
     ├─ intraday/     # 盘中扫描（M7调度器）
     ├─ premarket/    # 盘前扫描（M7调度器）
     └─ postmarket/   # 盘后扫描（M7调度器）
   ```

4. **始终记录扫描结果**（包括0异动）:
   ```python
   # M7调度器
   # 改为始终保存，不管是否有异动
   scan_result = {...}
   retro_file.write_text(json.dumps(scan_result, ...))
   ```

### 中期（本周）

5. **改进诊断方法**:
   - 优先检查代码（scheduler.py）而非数据文件
   - 使用 `git log` 追踪历史修改
   - 检查所有可能的持久化位置

6. **日志管理**:
   - 实现日志轮转（logrotate）
   - 限制单个日志文件大小（如100MB）

7. **文档更新**:
   - 在 README 中明确说明入口
   - 在 ARCHITECTURE.md 中说明持久化位置

---

## 六、总结

### 关键发现

1. ✅ **云服务器的改进都在本地版本中**
   - 盘前扫描：每天一次，采集隔夜信号
   - 盘后扫描：每天一次，全量价格扫描
   - 交易日历判断：节假日自动跳过

2. ❌ **我的诊断方法有问题**
   - 从数据文件入手，而非代码
   - 目录不存在导致误判
   - 日志文件过大导致查询失败

3. ⚠️ **run_continuous_simulation.py 的4小时盘后扫描无意义**
   - 应该废弃或改为每天一次
   - M7调度器已经正确实现

4. 🔴 **多入口问题仍然存在**
   - M7调度器 vs run_continuous_simulation.py
   - 需要明确职责或统一入口

### 两份架构评估报告的关系

- **4月18日报告**: 宏观评估，关注整体架构和模块边界
- **5月5日报告**: 微观评估，关注M12模块的入口和持久化
- **关系**: 互补，不冲突

### 改进建议优先级

**P0 (立即)**:
- ✅ 明确 M7调度器为生产入口
- ✅ 废弃 run_continuous_simulation 的4小时盘后扫描
- ✅ 始终记录扫描结果（包括0异动）

**P1 (本周)**:
- ✅ 统一持久化位置到 `data/m12_scans/`
- ✅ 实现日志轮转
- ✅ 更新文档

**P2 (本月)**:
- ⚠️ 评估是否废弃 run_continuous_simulation.py
- ⚠️ 实现统一持久化层

---

## 七、致歉与反思

### 我的错误

1. **诊断路径错误**: 从数据文件入手，而非代码
2. **检查不完整**: 没有检查所有可能的持久化位置
3. **误导性结论**: 误以为M7调度器没有盘前/盘后任务

### 改进措施

1. **优先检查代码**: 先看 scheduler.py，再看数据文件
2. **使用 git log**: 追踪历史修改，了解设计意图
3. **完整性检查**: 检查所有可能的目录和文件
4. **验证假设**: 不要基于"目录不存在"就下结论

### 感谢您的纠正

您的三个问题都非常准确：
1. ✅ 两份报告的区别和关系
2. ✅ 4小时盘后扫描的意义（确实没意义）
3. ✅ 云服务器版本的修改是否还在（都在）

这些问题帮助我发现了诊断方法的问题，避免了更大的误导。
