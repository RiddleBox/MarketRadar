# 问题3修复：持仓页面 KeyError

## 问题描述
持仓页面显示报错：`KeyError: 'cost_basis'`

错误堆栈：
```
File "D:\AIProjects\MarketRadar\dashboard_v2\pages\1_💼_持仓.py", line 88
    df_positions["current_price"] = df_positions["current_price"].fillna(df_positions["cost_basis"])
                                                                         ~~~~~~~~~~~~^^^^^^^^^^^^^^
KeyError: 'cost_basis'
```

## 根本原因
1. 使用了 `df_positions.get("cost_basis", 0)` 尝试从 DataFrame 获取列
2. DataFrame 的 `.get()` 方法返回的是列对象（Series），不是字典的 `.get()` 方法
3. 当 `cost_basis` 列不存在时，会抛出 KeyError

## 修复方案

### 修复前的错误代码
```python
if "current_price" not in df_positions.columns:
    df_positions["current_price"] = df_positions.get("cost_basis", 0)  # ❌ 错误

df_positions["current_price"] = df_positions["current_price"].fillna(df_positions["cost_basis"])  # ❌ 如果 cost_basis 不存在会报错
```

### 修复后的正确代码
```python
# 确保必需的列存在
if "cost_basis" not in df_positions.columns:
    st.error("持仓数据缺少 cost_basis 字段，请检查数据库")
    st.stop()

if "current_price" not in df_positions.columns:
    df_positions["current_price"] = df_positions["cost_basis"]  # ✅ 直接赋值列
else:
    df_positions["current_price"] = df_positions["current_price"].fillna(df_positions["cost_basis"])  # ✅ 使用 fillna
```

## 关键改进
1. **先检查必需列**：确保 `cost_basis` 列存在，否则显示错误并停止
2. **正确的列访问**：使用 `df["column"]` 而不是 `df.get("column")`
3. **清晰的逻辑**：分别处理列不存在和列存在但有缺失值的情况

## 影响文件
- `dashboard_v2/pages/1_💼_持仓.py` (line 84-92)

## 测试步骤
1. 访问持仓页面
2. 确认页面正常显示，无 KeyError
3. 确认盈亏计算正确

---

**修复时间**: 2026-05-06 22:03
**状态**: ✅ 已修复
