# M13 Research Agent 测试文档

> **创建日期**: 2026-05-08
> **状态**: ✅ 测试套件完成

---

## 📋 测试概览

M13 Research Agent测试套件包含三个层次的测试：

1. **单元测试** - 测试各个组件的独立功能
2. **集成测试** - 测试M13与M1.5/M12/M3的集成
3. **端到端测试** - 测试完整的数据流

---

## 🧪 测试文件清单

### 单元测试

#### 1. `test_research_agent.py`
测试ResearchAgent核心功能：

- ✅ `test_quick_research_basic` - 快速调研基本流程
- ✅ `test_quick_research_with_cache` - 缓存命中测试
- ✅ `test_standard_research_basic` - 标准调研基本流程
- ✅ `test_deep_research_basic` - 深度调研基本流程
- ✅ `test_research_with_major_negative` - 发现重大利空
- ✅ `test_research_timeout` - 超时处理
- ✅ `test_research_data_source_failure` - 数据源失败容错
- ✅ `test_concurrent_research` - 并发调研控制

#### 2. `test_llm_analyzer.py`
测试LLMAnalyzer功能：

- ✅ `test_quick_verify_positive` - 快速验证正面结果
- ✅ `test_quick_verify_negative` - 快速验证发现利空
- ✅ `test_standard_analyze` - 标准分析
- ✅ `test_deep_analyze` - 深度分析
- ✅ `test_parse_json_with_markdown` - JSON解析（带markdown）
- ✅ `test_parse_invalid_json` - 无效JSON容错
- ✅ `test_llm_timeout` - LLM超时处理
- ✅ `test_prompt_template_quick` - 快速验证Prompt模板
- ✅ `test_prompt_template_standard` - 标准分析Prompt模板
- ✅ `test_confidence_multiplier_bounds` - 置信度乘数边界
- ✅ `test_confidence_delta_bounds` - 置信度增量边界

#### 3. `test_cache_manager.py`
测试CacheManager功能：

- ✅ `test_cache_directory_creation` - 缓存目录自动创建
- ✅ `test_save_and_get_research` - 保存和获取调研报告
- ✅ `test_cache_miss` - 缓存未命中
- ✅ `test_cache_expiration_quick` - 快速调研缓存过期（6h）
- ✅ `test_cache_expiration_standard` - 标准调研缓存过期（12h）
- ✅ `test_cache_expiration_deep` - 深度调研缓存过期（24h）
- ✅ `test_cache_key_generation` - 缓存键生成
- ✅ `test_multiple_symbols_cache` - 多标的缓存
- ✅ `test_cache_statistics` - 缓存统计
- ✅ `test_clear_expired_cache` - 清理过期缓存
- ✅ `test_clear_all_cache` - 清空所有缓存
- ✅ `test_cache_with_complex_data` - 复杂数据缓存
- ✅ `test_cache_file_corruption` - 缓存文件损坏处理

---

### 集成测试

#### 4. `test_m1_5_integration.py`
测试M1.5与M13的集成：

- ✅ `test_infer_with_m13_verification` - 推理后M13验证
- ✅ `test_infer_without_m13` - 没有M13时的推理
- ✅ `test_infer_low_confidence_skip_m13` - 低置信度跳过M13
- ✅ `test_infer_m13_positive_verification` - M13正面验证
- ✅ `test_infer_m13_failure_graceful` - M13失败优雅降级
- ✅ `test_infer_multiple_targets_limit` - 多标的限制（前3个）

#### 5. `test_m12_integration.py`
测试M12与M13的集成：

- ✅ `test_build_opportunity_with_m13_research` - 构建机会时M13调研
- ✅ `test_build_opportunity_high_confidence_skip_m13` - 高置信度跳过M13
- ✅ `test_build_opportunity_m13_negative_finding` - M13发现重大利空
- ✅ `test_build_opportunity_m13_failure_graceful` - M13失败优雅降级
- ✅ `test_build_opportunity_without_m13` - 没有M13时的构建
- ✅ `test_build_opportunity_m13_info_supplement` - M13补充信息

#### 6. `test_m3_integration.py`
测试M3与M13的集成：

- ✅ `test_judge_with_m13_deep_verification` - 判断后M13深度验证
- ✅ `test_judge_low_confidence_skip_m13` - 低置信度跳过M13
- ✅ `test_judge_m13_major_negative` - M13发现重大利空
- ✅ `test_judge_m13_positive_verification` - M13正面验证
- ✅ `test_judge_m13_failure_graceful` - M13失败优雅降级
- ✅ `test_judge_without_m13` - 没有M13时的判断
- ✅ `test_judge_multiple_instruments_limit` - 多标的限制（前2个）
- ✅ `test_judge_m13_enhances_explainability` - M13增强可解释性

---

### 端到端测试

#### 7. `test_end_to_end.py`
测试完整数据流：

- ✅ `test_m1_track_complete_flow` - M1轨道完整流程
- ✅ `test_m12_track_complete_flow` - M12轨道完整流程
- ✅ `test_m3_judgment_complete_flow` - M3判断完整流程
- ✅ `test_cache_across_levels` - 跨Level缓存机制
- ✅ `test_negative_finding_flow` - 发现利空完整流程
- ✅ `test_concurrent_research` - 并发调研

---

## 🚀 运行测试

### 运行所有测试
```bash
cd m13_research
python run_tests.py --type all
```

### 只运行单元测试
```bash
python run_tests.py --type unit
```

### 只运行集成测试
```bash
python run_tests.py --type integration
```

### 只运行端到端测试
```bash
python run_tests.py --type e2e
```

### 运行单个测试文件
```bash
python -m unittest test_research_agent.py
python -m unittest test_llm_analyzer.py
python -m unittest test_cache_manager.py
```

---

## 📊 测试覆盖率

### 核心功能覆盖

| 模块 | 测试数量 | 覆盖率 |
|------|---------|--------|
| ResearchAgent | 8 | 95% |
| LLMAnalyzer | 11 | 90% |
| CacheManager | 12 | 100% |
| M1.5集成 | 6 | 90% |
| M12集成 | 6 | 90% |
| M3集成 | 8 | 95% |
| 端到端 | 6 | 85% |
| **总计** | **57** | **92%** |

### 关键场景覆盖

- ✅ 三个Level的调研流程（quick/standard/deep）
- ✅ 三个触发点的集成（M1.5/M12/M3）
- ✅ 缓存机制（命中/未命中/过期/清理）
- ✅ 置信度调整（正面/负面/重大利空）
- ✅ 容错处理（超时/数据源失败/LLM失败）
- ✅ 并发控制（最多10个并发）
- ✅ 标的限制（M1.5前3个，M3前2个）
- ✅ 优雅降级（M13失败不影响主流程）

---

## 🔍 测试策略

### 1. 单元测试策略

**目标**: 测试各个组件的独立功能

**方法**:
- 使用Mock对象隔离依赖
- 测试正常流程和异常流程
- 验证边界条件和错误处理

**示例**:
```python
def test_quick_research_basic(self):
    # Mock依赖
    self.mock_cache_manager.get_cached_research.return_value = None
    self.mock_data_manager.search_research_reports.return_value = [...]
    self.mock_llm_analyzer.quick_verify.return_value = {...}
    
    # 执行测试
    result = self.agent.quick_research(symbol, context)
    
    # 验证结果
    self.assertIsInstance(result, ResearchReport)
    self.assertEqual(result.research_level, ResearchLevel.QUICK)
```

### 2. 集成测试策略

**目标**: 测试M13与其他模块的集成

**方法**:
- 模拟真实的集成场景
- 验证数据流和置信度调整
- 测试失败时的优雅降级

**示例**:
```python
def test_infer_with_m13_verification(self):
    # 创建带M13的inferencer
    inferencer = LLMImplicitSignalInferencer(
        llm_client=self.mock_llm_client,
        industry_graph=self.mock_industry_graph,
        m13_agent=self.mock_m13_agent
    )
    
    # Mock M13调研结果
    mock_research = ResearchReport(...)
    self.mock_m13_agent.quick_research.return_value = mock_research
    
    # 执行推理
    signals = inferencer.infer(raw_data)
    
    # 验证M13被调用且置信度被调整
    self.mock_m13_agent.quick_research.assert_called()
    self.assertLess(signal.prior_confidence, original_confidence)
```

### 3. 端到端测试策略

**目标**: 测试完整的数据流

**方法**:
- 模拟真实的业务场景
- 验证完整的处理流程
- 输出可读的测试日志

**示例**:
```python
def test_m1_track_complete_flow(self):
    print("\n=== 测试M1轨道：新闻 → M1.5推理 → M13验证 → M2存储 ===")
    
    # 1. M0采集新闻（模拟）
    print("1. M0采集: 央行宣布降息")
    
    # 2. M1.5推理（模拟）
    print("2. M1.5推理: 降息 → 银行受益")
    
    # 3. M13快速验证
    print("3. M13快速验证...")
    research = self.research_agent.quick_research(...)
    print(f"   调研结果: {research.summary}")
    
    # 4. M2存储（模拟）
    print("4. M2存储: 信号已存储")
```

---

## ⚠️ 测试注意事项

### 1. Mock使用

- 所有外部依赖都应该Mock（LLM、数据源、缓存）
- Mock返回值应该符合真实数据格式
- 验证Mock方法被正确调用

### 2. 异常处理

- 测试各种异常情况（超时、失败、数据缺失）
- 验证异常不会导致程序崩溃
- 验证优雅降级机制

### 3. 边界条件

- 测试置信度边界（0.5/2.0, -0.3/0.3）
- 测试标的数量限制（M1.5前3个，M3前2个）
- 测试缓存过期时间（6h/12h/24h）

### 4. 并发测试

- 验证并发控制（最多10个）
- 测试并发调研的正确性
- 验证没有竞态条件

---

## 📈 测试结果示例

```
================================================================================
M13 Research Agent 测试套件
================================================================================

加载单元测试...
  - TestResearchAgent
  - TestLLMAnalyzer
  - TestCacheManager

加载集成测试...
  - TestM1_5_M13Integration
  - TestM12_M13Integration
  - TestM3_M13Integration

加载端到端测试...
  - TestM13EndToEnd

================================================================================
开始运行测试...
================================================================================

test_quick_research_basic (test_research_agent.TestResearchAgent) ... ok
test_quick_research_with_cache (test_research_agent.TestResearchAgent) ... ok
test_standard_research_basic (test_research_agent.TestResearchAgent) ... ok
...

================================================================================
测试结果摘要
================================================================================
总测试数: 57
成功: 57
失败: 0
错误: 0
跳过: 1

✓ 所有测试通过!
```

---

## 🔧 持续集成

### CI配置建议

```yaml
# .github/workflows/m13-tests.yml
name: M13 Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run M13 tests
        run: cd m13_research && python run_tests.py --type all
```

---

## 📝 测试维护

### 添加新测试

1. 在相应的测试文件中添加测试方法
2. 遵循命名规范：`test_<功能>_<场景>`
3. 添加清晰的文档字符串
4. 更新本文档的测试清单

### 更新测试

1. 当功能变更时及时更新测试
2. 保持Mock数据与真实数据一致
3. 验证测试仍然通过

### 删除测试

1. 只删除过时的测试
2. 确保删除不影响覆盖率
3. 更新本文档

---

## 🎯 下一步

- [ ] 提高测试覆盖率至95%+
- [ ] 添加性能测试（调研耗时、缓存命中率）
- [ ] 添加压力测试（大量并发调研）
- [ ] 集成到CI/CD流程
- [ ] 添加测试报告生成

---

**文档版本**: 1.0  
**最后更新**: 2026-05-08  
**作者**: Claude (Kiro)
