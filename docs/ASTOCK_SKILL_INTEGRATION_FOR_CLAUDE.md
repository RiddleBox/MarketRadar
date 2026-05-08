# A股数据SKILL集成方案 - Claude Code 实施指南

> **目标**：将现有的 A股数据SKILL 以最小改造方式集成到 MarketRadar 系统中，作为可插拔的信号源插件。

---

## 📍 背景信息

### 源文件位置
- **SKILL 文件**：`D:\AIProjects\Reference\4-封装SKILL：a-stock-data\a-stock-data-SKILL.md`
- **目标项目**：`D:\AIProjects\MarketRadar`

### SKILL 能力概览
这个 SKILL 是一个**自包含的 Markdown 文件**，提供以下数据层：

1. **行情层** (`tencent_quote`)
   - 实时行情数据（价格、涨跌幅、成交量等）
   - 数据源：腾讯财经 API

2. **研报层** (`eastmoney_reports`)
   - 券商研报列表（标题、评级、机构、日期）
   - 数据源：东方财富网

3. **新闻层** (`get_stock_news`)
   - 个股新闻（标题、来源、时间、链接）
   - 数据源：东方财富网

4. **估值计算** (`full_valuation`)
   - PE/PB/PEG 估值指标
   - 基于实时行情和财务数据计算

5. **基础数据层** (`get_stock_basic_info`)
   - 公司基本信息（名称、行业、市值等）

---

## 🎯 集成目标

### 核心需求
- **最小改造**：不重写 SKILL 代码，直接复用
- **插件化**：作为可插拔的信号源，不侵入现有架构
- **低耦合**：通过抽象接口和注册表解耦
- **可扩展**：未来可以轻松添加港股、美股等数据源

### 使用场景
1. **信号获取**：为 M0 数据采集器提供 A股市场信号
2. **数据源获取**：为 M3 推理引擎提供估值、研报、新闻等数据
3. **回测支持**：为回测系统提供历史数据（未来扩展）

---

## 🏗️ 架构设计

### 核心组件

```
MarketRadar/
├── integrations/
│   ├── astock_skill.py          # 从 SKILL.md 提取的代码模块
│   └── astock_signal_source.py  # SignalSource 插件实现
├── core/
│   └── signal_source_registry.py # 信号源注册表
├── config/
│   └── signal_sources.yaml       # 信号源配置文件
└── m0_collector/
    └── cli.py                    # 修改：注册 A股信号源
```

### 设计模式

#### 1. SignalSource 抽象接口
```python
class SignalSource(ABC):
    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """返回支持的能力列表"""
        pass
    
    @abstractmethod
    def fetch_signals(self, capability: str, params: dict) -> dict:
        """根据能力类型获取信号数据"""
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """健康检查"""
        pass
```

#### 2. 信号源注册表
```python
class SignalSourceRegistry:
    def register(self, name: str, source: SignalSource):
        """注册信号源"""
    
    def get_source(self, name: str) -> SignalSource:
        """获取信号源"""
    
    def list_capabilities(self) -> dict:
        """列出所有信号源的能力"""
    
    def fetch_by_capability(self, capability: str, params: dict) -> List[dict]:
        """根据能力从所有支持的信号源获取数据"""
```

#### 3. A股插件实现
```python
class AStockSignalSource(SignalSource):
    def get_capabilities(self):
        return ["valuation", "quotes", "reports", "news"]
    
    def fetch_signals(self, capability, params):
        if capability == "valuation":
            return astock_skill.full_valuation(params["symbol"])
        elif capability == "quotes":
            return astock_skill.tencent_quote(params["symbol"])
        # ... 其他能力
```

---

## 📋 实施步骤

### Step 1: 提取 SKILL 代码为 Python 模块

**文件**：`MarketRadar/integrations/astock_skill.py`

**任务**：
1. 从 `D:\AIProjects\Reference\4-封装SKILL：a-stock-data\a-stock-data-SKILL.md` 中提取所有 Python 代码块
2. 保持代码原样，不做修改
3. 确保所有依赖项都包含（requests, json, re 等）

**关键函数**：
- `tencent_quote(symbol)` - 行情数据
- `eastmoney_reports(symbol, page_size=20)` - 研报列表
- `get_stock_news(symbol, page_size=20)` - 个股新闻
- `full_valuation(symbol)` - 估值计算
- `get_stock_basic_info(symbol)` - 基础信息

**注意事项**：
- 保留所有辅助函数（如 `_parse_tencent_data`）
- 保留所有错误处理逻辑
- 不要修改 API 端点 URL

---

### Step 2: 创建 SignalSource 抽象接口

**文件**：`MarketRadar/core/signal_source_registry.py`

**任务**：
1. 定义 `SignalSource` 抽象基类
2. 实现 `SignalSourceRegistry` 注册表类
3. 提供能力发现和数据获取方法

**核心方法**：
```python
# SignalSource 接口
- get_capabilities() -> List[str]
- fetch_signals(capability: str, params: dict) -> dict
- health_check() -> bool

# SignalSourceRegistry
- register(name: str, source: SignalSource)
- get_source(name: str) -> SignalSource
- list_capabilities() -> dict
- fetch_by_capability(capability: str, params: dict) -> List[dict]
```

---

### Step 3: 实现 A股插件

**文件**：`MarketRadar/integrations/astock_signal_source.py`

**任务**：
1. 创建 `AStockSignalSource` 类，继承 `SignalSource`
2. 实现三个必需方法
3. 将 SKILL 函数映射到能力类型

**能力映射**：
```python
{
    "valuation": astock_skill.full_valuation,
    "quotes": astock_skill.tencent_quote,
    "reports": astock_skill.eastmoney_reports,
    "news": astock_skill.get_stock_news
}
```

**错误处理**：
- 网络请求失败 → 返回空结果 + 错误信息
- 数据解析失败 → 记录日志 + 返回部分数据
- 健康检查失败 → 标记为不可用

---

### Step 4: 创建配置文件

**文件**：`MarketRadar/config/signal_sources.yaml`

**任务**：
1. 定义 A股信号源的配置
2. 支持启用/禁用开关
3. 支持参数配置（如默认页大小）

**配置示例**：
```yaml
signal_sources:
  astock:
    enabled: true
    class: "integrations.astock_signal_source.AStockSignalSource"
    params:
      default_page_size: 20
      timeout: 10
```

---

### Step 5: 注册到 M0 采集器

**文件**：`MarketRadar/m0_collector/cli.py`

**任务**：
1. 在 M0 初始化时加载信号源配置
2. 注册 A股信号源到注册表
3. 提供 CLI 命令测试信号源

**修改点**：
```python
def init_signal_sources():
    """初始化信号源注册表"""
    registry = SignalSourceRegistry()
    
    # 加载配置
    config = load_yaml("config/signal_sources.yaml")
    
    # 注册 A股信号源
    if config["signal_sources"]["astock"]["enabled"]:
        astock_source = AStockSignalSource()
        registry.register("astock", astock_source)
    
    return registry
```

---

### Step 6: 测试验证

**测试脚本**：`MarketRadar/tests/test_astock_integration.py`

**测试用例**：
1. **能力发现测试**
   ```python
   capabilities = registry.list_capabilities()
   assert "astock" in capabilities
   assert "valuation" in capabilities["astock"]
   ```

2. **数据获取测试**
   ```python
   result = registry.fetch_by_capability("valuation", {"symbol": "600519"})
   assert result is not None
   assert "pe" in result
   ```

3. **健康检查测试**
   ```python
   source = registry.get_source("astock")
   assert source.health_check() == True
   ```

4. **错误处理测试**
   ```python
   result = registry.fetch_by_capability("valuation", {"symbol": "INVALID"})
   assert "error" in result
   ```

---

## 🔧 实施建议

### 开发顺序
1. **先实现核心接口**（SignalSource + Registry）
2. **再提取 SKILL 代码**（确保代码可运行）
3. **然后实现插件**（连接接口和 SKILL）
4. **最后集成到 M0**（注册和测试）

### 测试策略
- **单元测试**：每个组件独立测试
- **集成测试**：端到端测试信号获取流程
- **手动测试**：使用真实股票代码验证数据准确性

### 扩展路径
未来添加新数据源（如港股、美股）只需：
1. 创建新的 `XXXSignalSource` 类
2. 在配置文件中添加配置
3. 在 M0 初始化时注册

---

## 🚨 注意事项

### 代码提取
- **不要修改 SKILL 代码**：直接复制粘贴，保持原样
- **保留所有注释**：SKILL 中的注释包含重要的使用说明
- **测试所有函数**：确保提取后的代码可以独立运行

### 依赖管理
- **检查依赖项**：确保 `requests` 等库已安装
- **版本兼容性**：SKILL 使用 Python 3.7+ 特性

### 错误处理
- **网络请求**：添加超时和重试机制
- **数据解析**：处理 API 返回格式变化
- **日志记录**：记录所有错误和警告

### 性能优化
- **缓存机制**：避免频繁请求相同数据
- **并发控制**：限制同时请求数量
- **速率限制**：遵守 API 调用频率限制

---

## 📊 预期成果

### 功能验证
- [ ] 可以通过注册表获取 A股估值数据
- [ ] 可以通过注册表获取 A股行情数据
- [ ] 可以通过注册表获取 A股研报列表
- [ ] 可以通过注册表获取 A股新闻列表
- [ ] 健康检查正常工作
- [ ] 配置文件可以控制启用/禁用

### 代码质量
- [ ] 所有代码通过单元测试
- [ ] 所有代码通过集成测试
- [ ] 代码符合项目规范（PEP 8）
- [ ] 代码有完整的文档字符串

### 架构验证
- [ ] 插件可以独立启用/禁用
- [ ] 添加新数据源不需要修改现有代码
- [ ] M0 采集器可以透明使用信号源

---

## 🤝 与 Claude Code 协作建议

### 讨论重点
1. **代码提取策略**：如何从 Markdown 中提取代码？是否需要自动化脚本？
2. **接口设计细节**：`fetch_signals` 的返回格式是否需要标准化？
3. **错误处理策略**：如何优雅地处理 API 失败？
4. **测试覆盖率**：需要哪些额外的测试用例？
5. **性能优化**：是否需要添加缓存？如何实现？

### 可以请 Claude Code 帮助的任务
- 从 SKILL.md 中提取代码并格式化
- 实现 SignalSource 接口和注册表
- 编写单元测试和集成测试
- 优化错误处理和日志记录
- 添加缓存和性能优化

### 需要人工决策的问题
- 是否需要修改 SKILL 代码以适应项目规范？
- 是否需要添加额外的数据验证逻辑？
- 是否需要实现数据缓存机制？
- 是否需要支持异步请求？

---

## 📚 参考资料

### 项目文档
- MarketRadar 架构文档：`docs/architecture.md`
- M0 采集器文档：`docs/m0_collector.md`

### SKILL 文档
- A股数据SKILL：`D:\AIProjects\Reference\4-封装SKILL：a-stock-data\a-stock-data-SKILL.md`

### 相关技术
- Python ABC (抽象基类)：https://docs.python.org/3/library/abc.html
- YAML 配置：https://pyyaml.org/wiki/PyYAMLDocumentation
- Requests 库：https://requests.readthedocs.io/

---

## ✅ 下一步行动

1. **在 VSCode 中打开 MarketRadar 项目**
2. **将此文档分享给 Claude Code**
3. **与 Claude Code 讨论实施细节**
4. **逐步实现各个组件**
5. **运行测试验证功能**

---

**预计工作量**：2-3 小时（包括编码、测试、调试）

**难度评估**：中等（主要是代码提取和接口设计，逻辑不复杂）

**风险点**：
- SKILL 代码提取可能遗漏依赖
- API 端点可能失效（需要测试验证）
- 数据格式可能与预期不符（需要调试）

---

祝实施顺利！有任何问题随时在 Claude Code 中讨论。🚀
