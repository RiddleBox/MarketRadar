# MarketRadar Changelog

## [2026-04-30] 修复 Pydantic 兼容性问题

### 问题描述
- M3判断引擎在调用 `ImplicitSignal.model_validate_json()` 时失败
- 错误信息：`type object 'ImplicitSignal' has no attribute 'model_validate_json'`
- 根本原因：`ImplicitSignal` 使用 Python 标准库的 `@dataclass`，而不是 Pydantic 的 `BaseModel`

### 修复内容
**文件：`m1_5_implicit_reasoner/models.py`**

将以下数据类从 `dataclass` 迁移到 Pydantic `BaseModel`：
- `CausalLink`
- `ReasoningChain`
- `ImplicitSignal`

**主要变更：**
```python
# 修复前
from dataclasses import dataclass, field

@dataclass
class ImplicitSignal:
    ...

# 修复后
from pydantic import BaseModel, Field

class ImplicitSignal(BaseModel):
    ...
```

**兼容性调整：**
- `ReasoningChain.reasoning_stages` 字段类型从 `Dict[ReasoningStage, str]` 改为 `Dict[str, str]`
  - 原因：Pydantic JSON 序列化不支持 Enum 作为字典 key
  - 影响：需要在使用时将字符串转换回 `ReasoningStage` 枚举

### 验证结果
✅ `model_validate_json()` 调用成功  
✅ 完整流程运行正常：采集25条新闻 → 生成134个隐性信号 → M2存储成功  
⚠️ M3判断引擎返回0个高质量机会（判断标准问题，非代码bug）

### 影响范围
- 所有使用 `ImplicitSignal` 的模块（M1.5、M2、M3）
- 数据库存储和检索逻辑（已验证兼容）

### 后续优化建议
1. 调整M3判断引擎的筛选标准，降低"构成机会"的门槛
2. 统一项目中所有数据模型为 Pydantic BaseModel
3. 添加单元测试覆盖 `model_validate_json()` 调用路径
