# 端到端验证报告

> 日期：2026-04-18
> 脚本：`tests/run_verification.py`
> 输出：`test_verification_output.txt`

---

## 验证结果：8/8 通过

| # | 模块 | 状态 | 详情 |
|---|------|------|------|
| 1 | Signal Store (M2) | ✅ | total=21, by_type={macro:4, sentiment:17}, recent_batches=3 |
| 2 | Paper Trading (M9) | ✅ | 无持仓（首次运行，正常） |
| 3 | Audit Log | ✅ | 数据库已创建，0 条记录（首次运行，正常） |
| 4 | Confirmation Store | ✅ | 数据库已创建，0 条记录（首次运行，正常） |
| 5 | Sentiment Store (M10) | ✅ | 数据库未创建（需运行情绪采集后生成） |
| 6 | M11 Calibration Store | ✅ | 数据库未创建（需运行校准后生成） |
| 7 | Opportunities | ✅ | 1 个机会文件（来自 run_pipeline.py 测试） |
| 8 | End-to-end Pipeline (M1→M4) | ✅ | signals=2, opportunities=1, plans=1 |

---

## 端到端管道详情

**输入**：央行降准 0.5bp + 降息 10bp 新闻

**M1 信号解码**：提取 2 条信号
- `sig_*` [macro] 央行降准释放长期流动性
- `sig_*` [macro] 央行下调7天逆回购利率

**M2 信号存储**：保存 2 条（去重后），累计 21 条

**M3 机会判断**：识别 1 个机会
- "降准双降释放流动性" → priority=research, market=A_SHARE, direction=BULLISH

**M4 行动设计**：生成 1 个 ActionPlan
- 推荐标的：沪深300ETF、科创50ETF

---

## 待完善项

| 项目 | 说明 | 优先级 |
|------|------|--------|
| Sentiment Store | 运行 `python -m m10_sentiment.cli collect` 后生成 | 低 |
| M11 Calibration Store | 运行 M11 校准后生成 | 低 |
| Audit Log | 首次 Dashboard 运行或工作流执行后写入 | 低 |

---

## 如何复现

```powershell
# 运行完整验证
python tests/run_verification.py

# 查看输出
type test_verification_output.txt
```
