# A股数据SKILL集成实施计划

## 📋 概述

本文档提供将 `a-stock-data-SKILL.md` 集成到 MarketRadar 的完整实施指南。

**SKILL 源文件**：`D:\AIProjects\Reference\4-封装SKILL：a-stock-data\4-封装SKILL：a-stock-data\a-stock-data-SKILL.md`  
**集成方式**：零重写方案 - 直接提取SKILL代码封装为SignalSource插件  
**预计工作量**：2小时  
**改造成本**：最小（无需重构现有代码）

**SKILL 能力概览**：
- **行情层**：mootdx (K线+五档盘口) + 腾讯财经 (PE/PB/市值/换手率)
- **研报层**：东财研报API + akshare一致预期EPS + iwencai语义搜索
- **新闻层**：个股新闻 + 财联社快讯 + 东财全球资讯
- **基础数据层**：mootdx财务快照 + F10公司资料 + akshare基本面
- **公告层**：巨潮公告 + mootdx公告摘要

---

## 🎯 集成目标

将A股数据SKILL的五层能力集成到MarketRadar信号采集系统：

1. **行情层**：实时报价、市值、换手率
2. **研报层**：东财研报列表
3. **新闻层**：个股新闻聚合
4. **估值层**：PE/PB/PEG/消化时间计算
5. **基础数据层**：财务快照

---

## 📁 文件结构

```
MarketRadar/
├── integrations/
│   ├── __init__.py
│   ├── astock_skill.py          # [新建] SKILL核心函数提取
│   └── astock_signal_source.py  # [新建] SignalSource插件封装
├── config/
│   └── signal_sources.yaml      # [新建] 信号源配置
├── m0_collector/
│   ├── __init__.py
│   ├── cli.py                   # [修改] 注册信号源
│   └── signal_registry.py       # [新建] 信号源注册表
└── docs/
    └── ASTOCK_SKILL_INTEGRATION_PLAN.md  # 本文档
```

---

## 🔧 实施步骤

### 步骤 1：创建信号源注册表基础设施

**文件**：`m0_collector/signal_registry.py`

```python
"""
信号源注册表 - 管理可插拔信号源
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class SignalSource(ABC):
    """信号源抽象接口"""
    
    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """返回支持的能力列表"""
        pass
    
    @abstractmethod
    def fetch_signals(self, capability: str, params: Dict) -> List[Dict]:
        """
        获取信号数据
        
        Args:
            capability: 能力名称（如 'valuation', 'quotes'）
            params: 查询参数（如 {'symbol': '000001.SZ'}）
        
        Returns:
            信号数据列表
        """
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """健康检查"""
        pass


class SignalSourceRegistry:
    """信号源注册表"""
    
    def __init__(self):
        self._sources: Dict[str, SignalSource] = {}
        self._capability_map: Dict[str, List[str]] = {}  # capability -> [source_names]
    
    def register(self, name: str, source: SignalSource):
        """注册信号源"""
        self._sources[name] = source
        
        # 更新能力映射
        for cap in source.get_capabilities():
            if cap not in self._capability_map:
                self._capability_map[cap] = []
            self._capability_map[cap].append(name)
        
        logger.info(f"✅ 注册信号源: {name}, 能力: {source.get_capabilities()}")
    
    def fetch_by_capability(self, capability: str, params: Dict) -> List[Dict]:
        """根据能力获取信号"""
        if capability not in self._capability_map:
            logger.warning(f"⚠️ 未找到支持 '{capability}' 的信号源")
            return []
        
        results = []
        for source_name in self._capability_map[capability]:
            source = self._sources[source_name]
            try:
                data = source.fetch_signals(capability, params)
                results.extend(data)
            except Exception as e:
                logger.error(f"❌ 信号源 {source_name} 获取 {capability} 失败: {e}")
        
        return results
    
    def list_capabilities(self) -> Dict[str, List[str]]:
        """列出所有能力及其提供者"""
        return self._capability_map.copy()
    
    def health_check_all(self) -> Dict[str, bool]:
        """检查所有信号源健康状态"""
        return {name: source.health_check() for name, source in self._sources.items()}


# 全局注册表实例
_registry = SignalSourceRegistry()


def get_registry() -> SignalSourceRegistry:
    """获取全局注册表"""
    return _registry
```

**操作指令**：
```bash
# 在 VSCode 中
# 1. 打开 MarketRadar 项目
# 2. 右键 m0_collector 文件夹 → 新建文件 → signal_registry.py
# 3. 复制上述代码粘贴
# 4. Ctrl+S 保存
```

---

### 步骤 2：提取SKILL核心函数

**文件**：`integrations/astock_skill.py`

```python
"""
A股数据SKILL核心函数提取
从 a-stock-data-SKILL.md 中提取的数据获取函数
"""
import requests
import akshare as ak
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


# ============================================================
# 行情层：腾讯实时行情
# ============================================================
def tencent_quote(symbol: str) -> Optional[Dict]:
    """
    腾讯实时行情接口
    
    Args:
        symbol: 股票代码，如 '000001' 或 '600000'
    
    Returns:
        {
            'symbol': '000001.SZ',
            'name': '平安银行',
            'price': 12.34,
            'change_pct': 1.23,
            'volume': 123456789,
            'turnover': 1234567890.0,
            'market_cap': 123456789012.0,
            'pe_ttm': 5.67,
            'pb': 0.89
        }
    """
    try:
        # 判断市场
        market_code = 'sz' if symbol.startswith(('0', '3')) else 'sh'
        full_code = f"{market_code}{symbol}"
        
        url = f"http://qt.gtimg.cn/q={full_code}"
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        
        # 解析返回数据
        data = resp.text.split('~')
        if len(data) < 50:
            return None
        
        return {
            'symbol': f"{symbol}.{'SZ' if market_code == 'sz' else 'SH'}",
            'name': data[1],
            'price': float(data[3]),
            'change_pct': float(data[32]),
            'volume': int(data[6]),
            'turnover': float(data[37]),
            'market_cap': float(data[45]) * 100000000,  # 亿转元
            'pe_ttm': float(data[39]) if data[39] else None,
            'pb': float(data[46]) if data[46] else None
        }
    except Exception as e:
        logger.error(f"腾讯行情获取失败 {symbol}: {e}")
        return None


# ============================================================
# 研报层：东方财富研报
# ============================================================
def eastmoney_reports(symbol: str, limit: int = 20) -> List[Dict]:
    """
    东方财富研报列表
    
    Args:
        symbol: 股票代码，如 '000001'
        limit: 返回数量
    
    Returns:
        [
            {
                'title': '研报标题',
                'institution': '机构名称',
                'analyst': '分析师',
                'rating': '买入',
                'publish_date': '2024-05-07',
                'url': 'https://...'
            }
        ]
    """
    try:
        df = ak.stock_research_report_em(symbol=symbol)
        if df.empty:
            return []
        
        df = df.head(limit)
        return df.to_dict('records')
    except Exception as e:
        logger.error(f"东财研报获取失败 {symbol}: {e}")
        return []


# ============================================================
# 新闻层：个股新闻
# ============================================================
def get_stock_news(symbol: str, limit: int = 10) -> List[Dict]:
    """
    个股新闻聚合（东财+新浪）
    
    Args:
        symbol: 股票代码，如 '000001'
        limit: 返回数量
    
    Returns:
        [
            {
                'title': '新闻标题',
                'source': '来源',
                'publish_time': '2024-05-07 10:30:00',
                'url': 'https://...',
                'summary': '摘要'
            }
        ]
    """
    try:
        # 东财新闻
        df = ak.stock_news_em(symbol=symbol)
        if df.empty:
            return []
        
        df = df.head(limit)
        return df.to_dict('records')
    except Exception as e:
        logger.error(f"个股新闻获取失败 {symbol}: {e}")
        return []


# ============================================================
# 估值层：完整估值计算
# ============================================================
def full_valuation(symbol: str) -> Optional[Dict]:
    """
    完整估值分析（PE/PB/PEG/消化时间）
    
    Args:
        symbol: 股票代码，如 '000001'
    
    Returns:
        {
            'symbol': '000001.SZ',
            'pe_ttm': 12.34,
            'pb': 1.23,
            'peg': 0.89,
            'digest_years': 2.5,  # PE消化时间
            'valuation_level': 'reasonable'  # cheap/reasonable/expensive
        }
    """
    try:
        quote = tencent_quote(symbol)
        if not quote:
            return None
        
        pe = quote.get('pe_ttm')
        pb = quote.get('pb')
        
        if not pe or not pb:
            return None
        
        # 简化估值判断逻辑
        valuation_level = 'reasonable'
        if pe < 15 and pb < 1.5:
            valuation_level = 'cheap'
        elif pe > 30 or pb > 3:
            valuation_level = 'expensive'
        
        return {
            'symbol': quote['symbol'],
            'pe_ttm': pe,
            'pb': pb,
            'peg': None,  # 需要增长率数据
            'digest_years': pe / 15 if pe else None,  # 假设15%增长
            'valuation_level': valuation_level
        }
    except Exception as e:
        logger.error(f"估值计算失败 {symbol}: {e}")
        return None


# ============================================================
# 基础数据层：财务快照
# ============================================================
def get_financial_snapshot(symbol: str) -> Optional[Dict]:
    """
    财务快照（最新季度）
    
    Args:
        symbol: 股票代码，如 '000001'
    
    Returns:
        {
            'symbol': '000001.SZ',
            'revenue': 123456789.0,
            'net_profit': 12345678.0,
            'roe': 12.34,
            'debt_ratio': 0.45,
            'report_date': '2024-03-31'
        }
    """
    try:
        # 使用 akshare 获取财务数据
        df = ak.stock_financial_abstract_em(symbol=symbol)
        if df.empty:
            return None
        
        latest = df.iloc[0]
        return {
            'symbol': f"{symbol}.{'SZ' if symbol.startswith(('0', '3')) else 'SH'}",
            'revenue': latest.get('营业总收入'),
            'net_profit': latest.get('净利润'),
            'roe': latest.get('净资产收益率'),
            'debt_ratio': latest.get('资产负债率'),
            'report_date': latest.get('报告期')
        }
    except Exception as e:
        logger.error(f"财务快照获取失败 {symbol}: {e}")
        return None
```

**操作指令**：
```bash
# 在 VSCode 中
# 1. 右键 integrations 文件夹 → 新建文件 → astock_skill.py
# 2. 复制上述代码粘贴
# 3. Ctrl+S 保存
```

---

### 步骤 3：封装SignalSource插件

**文件**：`integrations/astock_signal_source.py`

```python
"""
A股数据信号源插件
将 astock_skill 封装为 SignalSource 接口
"""
from typing import Dict, List
import logging
from m0_collector.signal_registry import SignalSource
from integrations import astock_skill

logger = logging.getLogger(__name__)


class AStockSignalSource(SignalSource):
    """A股数据信号源"""
    
    def __init__(self):
        self._capabilities = [
            'valuation',      # 估值数据
            'quotes',         # 实时行情
            'reports',        # 研报列表
            'news',           # 个股新闻
            'financials'      # 财务快照
        ]
    
    def get_capabilities(self) -> List[str]:
        return self._capabilities
    
    def fetch_signals(self, capability: str, params: Dict) -> List[Dict]:
        """
        获取信号数据
        
        Args:
            capability: 能力名称
            params: 必须包含 'symbol' 字段（如 '000001'）
        
        Returns:
            信号数据列表
        """
        symbol = params.get('symbol')
        if not symbol:
            logger.error("❌ 缺少 symbol 参数")
            return []
        
        # 标准化股票代码（去除市场后缀）
        symbol = symbol.split('.')[0]
        
        try:
            if capability == 'valuation':
                data = astock_skill.full_valuation(symbol)
                return [data] if data else []
            
            elif capability == 'quotes':
                data = astock_skill.tencent_quote(symbol)
                return [data] if data else []
            
            elif capability == 'reports':
                limit = params.get('limit', 20)
                return astock_skill.eastmoney_reports(symbol, limit)
            
            elif capability == 'news':
                limit = params.get('limit', 10)
                return astock_skill.get_stock_news(symbol, limit)
            
            elif capability == 'financials':
                data = astock_skill.get_financial_snapshot(symbol)
                return [data] if data else []
            
            else:
                logger.warning(f"⚠️ 不支持的能力: {capability}")
                return []
        
        except Exception as e:
            logger.error(f"❌ 获取 {capability} 失败: {e}")
            return []
    
    def health_check(self) -> bool:
        """健康检查：测试腾讯行情接口"""
        try:
            result = astock_skill.tencent_quote('000001')
            return result is not None
        except:
            return False
```

**操作指令**：
```bash
# 在 VSCode 中
# 1. 右键 integrations 文件夹 → 新建文件 → astock_signal_source.py
# 2. 复制上述代码粘贴
# 3. Ctrl+S 保存
```

---

### 步骤 4：创建配置文件

**文件**：`config/signal_sources.yaml`

```yaml
# 信号源配置文件

signal_sources:
  astock:
    enabled: true
    description: "A股数据SKILL - 提供行情/研报/新闻/估值/财务数据"
    capabilities:
      - valuation
      - quotes
      - reports
      - news
      - financials
    
    # 采集参数
    params:
      default_limit: 20        # 默认返回数量
      timeout: 5               # 请求超时（秒）
      retry_times: 2           # 重试次数
    
    # 健康检查
    health_check:
      enabled: true
      interval: 300            # 检查间隔（秒）
      test_symbol: "000001"    # 测试用股票代码
```

**操作指令**：
```bash
# 在 VSCode 中
# 1. 右键 config 文件夹 → 新建文件 → signal_sources.yaml
# 2. 复制上述代码粘贴
# 3. Ctrl+S 保存
```

---

### 步骤 5：注册信号源到M0采集器

**文件**：`m0_collector/cli.py`（修改现有文件）

在文件开头添加导入：

```python
# 在现有导入后添加
from m0_collector.signal_registry import get_registry
from integrations.astock_signal_source import AStockSignalSource
import yaml
```

在 `main()` 函数或初始化逻辑中添加注册代码：

```python
def initialize_signal_sources():
    """初始化信号源"""
    registry = get_registry()
    
    # 读取配置
    config_path = "config/signal_sources.yaml"
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        logger.warning(f"⚠️ 配置文件不存在: {config_path}")
        return
    
    # 注册A股信号源
    if config['signal_sources']['astock']['enabled']:
        astock_source = AStockSignalSource()
        registry.register('astock', astock_source)
        logger.info("✅ A股信号源已注册")
    
    # 健康检查
    health = registry.health_check_all()
    logger.info(f"📊 信号源健康状态: {health}")


# 在 main() 函数开头调用
def main():
    initialize_signal_sources()
    # ... 原有逻辑
```

**操作指令**：
```bash
# 在 VSCode 中
# 1. 打开 m0_collector/cli.py
# 2. 在文件开头添加导入语句
# 3. 在 main() 函数前添加 initialize_signal_sources() 函数
# 4. 在 main() 函数开头调用 initialize_signal_sources()
# 5. Ctrl+S 保存
```

---

### 步骤 6：使用信号源（示例）

在任何需要A股数据的地方，通过注册表调用：

```python
from m0_collector.signal_registry import get_registry

# 获取注册表
registry = get_registry()

# 获取估值数据
valuation = registry.fetch_by_capability('valuation', {'symbol': '000001'})
print(valuation)

# 获取实时行情
quotes = registry.fetch_by_capability('quotes', {'symbol': '600000'})
print(quotes)

# 获取研报
reports = registry.fetch_by_capability('reports', {'symbol': '000001', 'limit': 10})
print(reports)
```

---

## ✅ 验证测试

### 测试脚本

创建 `test_astock_integration.py`：

```python
"""
A股信号源集成测试
"""
import sys
sys.path.insert(0, '.')

from m0_collector.signal_registry import get_registry
from integrations.astock_signal_source import AStockSignalSource


def test_registration():
    """测试注册"""
    registry = get_registry()
    source = AStockSignalSource()
    registry.register('astock', source)
    
    print("✅ 注册成功")
    print(f"📋 支持的能力: {registry.list_capabilities()}")


def test_valuation():
    """测试估值数据"""
    registry = get_registry()
    data = registry.fetch_by_capability('valuation', {'symbol': '000001'})
    
    print("\n📊 估值数据:")
    print(data)


def test_quotes():
    """测试实时行情"""
    registry = get_registry()
    data = registry.fetch_by_capability('quotes', {'symbol': '600000'})
    
    print("\n💹 实时行情:")
    print(data)


def test_reports():
    """测试研报"""
    registry = get_registry()
    data = registry.fetch_by_capability('reports', {'symbol': '000001', 'limit': 5})
    
    print("\n📄 研报列表:")
    for report in data:
        print(f"  - {report.get('title', 'N/A')}")


def test_health():
    """测试健康检查"""
    registry = get_registry()
    health = registry.health_check_all()
    
    print("\n🏥 健康状态:")
    print(health)


if __name__ == '__main__':
    test_registration()
    test_valuation()
    test_quotes()
    test_reports()
    test_health()
```

**运行测试**：
```bash
cd /mnt/d/AIProjects/MarketRadar
python test_astock_integration.py
```

**预期输出**：
```
✅ 注册成功
📋 支持的能力: {'valuation': ['astock'], 'quotes': ['astock'], ...}

📊 估值数据:
[{'symbol': '000001.SZ', 'pe_ttm': 5.23, 'pb': 0.67, ...}]

💹 实时行情:
[{'symbol': '600000.SH', 'name': '浦发银行', 'price': 8.12, ...}]

📄 研报列表:
  - 平安银行：资产质量持续改善，维持买入评级
  - ...

🏥 健康状态:
{'astock': True}
```

---

## 🚀 后续扩展

### 1. 添加更多能力

在 `astock_skill.py` 中添加新函数，然后在 `AStockSignalSource` 中注册：

```python
# astock_skill.py
def get_announcements(symbol: str, limit: int = 10) -> List[Dict]:
    """获取公告列表"""
    # 实现逻辑
    pass

# astock_signal_source.py
class AStockSignalSource(SignalSource):
    def __init__(self):
        self._capabilities = [
            'valuation', 'quotes', 'reports', 'news', 'financials',
            'announcements'  # 新增
        ]
    
    def fetch_signals(self, capability: str, params: Dict) -> List[Dict]:
        # ...
        elif capability == 'announcements':
            limit = params.get('limit', 10)
            return astock_skill.get_announcements(symbol, limit)
```

### 2. 集成到M3判断引擎

在 `m3_judgment` 模块中使用信号源：

```python
from m0_collector.signal_registry import get_registry

def analyze_stock(symbol: str):
    registry = get_registry()
    
    # 获取多维度数据
    valuation = registry.fetch_by_capability('valuation', {'symbol': symbol})
    news = registry.fetch_by_capability('news', {'symbol': symbol, 'limit': 5})
    reports = registry.fetch_by_capability('reports', {'symbol': symbol, 'limit': 3})
    
    # 综合判断逻辑
    # ...
```

### 3. 添加缓存层

在 `signal_registry.py` 中添加缓存：

```python
from functools import lru_cache
from datetime import datetime, timedelta

class CachedSignalSource(SignalSource):
    def __init__(self, source: SignalSource, ttl: int = 300):
        self._source = source
        self._cache = {}
        self._ttl = ttl
    
    def fetch_signals(self, capability: str, params: Dict) -> List[Dict]:
        cache_key = f"{capability}:{params.get('symbol')}"
        
        if cache_key in self._cache:
            data, timestamp = self._cache[cache_key]
            if datetime.now() - timestamp < timedelta(seconds=self._ttl):
                return data
        
        data = self._source.fetch_signals(capability, params)
        self._cache[cache_key] = (data, datetime.now())
        return data
```

---

## 📝 注意事项

1. **依赖安装**：确保已安装 `akshare` 和 `requests`
   ```bash
   pip install akshare requests pyyaml
   ```

2. **股票代码格式**：
   - 输入：纯数字代码（如 `'000001'`, `'600000'`）
   - 输出：带市场后缀（如 `'000001.SZ'`, `'600000.SH'`）

3. **错误处理**：所有函数都有异常捕获，失败时返回 `None` 或空列表

4. **日志记录**：使用 `logging` 模块记录所有操作，便于调试

5. **健康检查**：定期运行 `registry.health_check_all()` 监控信号源状态

---

## 🎉 完成标志

集成完成后，你应该能够：

- ✅ 通过 `registry.list_capabilities()` 看到 A股信号源的5种能力
- ✅ 通过 `registry.fetch_by_capability()` 获取任意A股数据
- ✅ 在 M0/M3 模块中无缝使用 A股数据增强判断逻辑
- ✅ 通过配置文件启用/禁用信号源，无需修改代码

---

## 📞 问题排查

### 问题1：导入错误 `ModuleNotFoundError`

**原因**：Python 路径未包含项目根目录

**解决**：
```python
import sys
sys.path.insert(0, '/mnt/d/AIProjects/MarketRadar')
```

### 问题2：腾讯行情接口返回空数据

**原因**：股票代码格式错误或市场判断错误

**解决**：检查 `tencent_quote()` 中的市场代码逻辑

### 问题3：akshare 函数调用失败

**原因**：akshare 版本过旧或API变更

**解决**：
```bash
pip install --upgrade akshare
```

---

**文档版本**：v1.0  
**最后更新**：2025-05-07  
**作者**：信标 (Beacon)
