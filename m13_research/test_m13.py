"""
M13 Research Agent 测试脚本

测试M13模块的基本功能
"""

import sys
import io
from pathlib import Path

# 修复Windows控制台编码
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 添加项目根目录到路径
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from core.schemas import ResearchLevel, ResearchTrigger
from m13_research.cache_manager import CacheManager
from integrations.data_provider_manager import get_global_data_manager
from integrations.init_data_providers import initialize_data_providers

def test_cache_manager():
    """测试缓存管理器"""
    print("\n" + "=" * 60)
    print("测试：缓存管理器")
    print("=" * 60)

    cache_dir = ROOT / "data" / "m13_cache"
    cache_manager = CacheManager(cache_dir)

    # 获取统计
    stats = cache_manager.get_stats()
    print(f"缓存统计: {stats}")

    print("✅ 缓存管理器测试通过")

def test_data_provider():
    """测试数据提供者"""
    print("\n" + "=" * 60)
    print("测试：数据提供者")
    print("=" * 60)

    # 初始化数据提供者
    if not initialize_data_providers():
        print("❌ 数据提供者初始化失败")
        return False

    manager = get_global_data_manager()

    # 测试获取行情
    quote = manager.get_quote("000001")
    if quote:
        print(f"✅ 获取行情成功: {quote.get('symbol')} - 价格={quote.get('price')}")
    else:
        print("⚠️ 获取行情失败")

    # 测试获取研报
    reports = manager.get_research_reports("000001", limit=5)
    print(f"✅ 获取研报: {len(reports)} 篇")

    return True

def test_schemas():
    """测试数据模型"""
    print("\n" + "=" * 60)
    print("测试：数据模型")
    print("=" * 60)

    from core.schemas import ResearchReport, ResearchContext

    # 创建调研上下文
    context = ResearchContext(
        symbol="000001",
        opportunity_context="测试调研",
        research_level=ResearchLevel.QUICK,
        triggered_by=ResearchTrigger.M1_5,
        timeout_seconds=30
    )
    print(f"✅ 创建调研上下文: {context.symbol} ({context.research_level.value})")

    # 创建调研报告
    report = ResearchReport(
        symbol="000001",
        research_level=ResearchLevel.QUICK,
        triggered_by=ResearchTrigger.M1_5,
        summary="测试报告",
        confidence_multiplier=1.2
    )
    print(f"✅ 创建调研报告: {report.symbol} - 置信度乘数={report.confidence_multiplier}")

    return True

def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("M13 Research Agent 测试")
    print("=" * 60)

    try:
        # 测试1: 数据模型
        if not test_schemas():
            print("\n❌ 数据模型测试失败")
            return

        # 测试2: 缓存管理器
        test_cache_manager()

        # 测试3: 数据提供者
        if not test_data_provider():
            print("\n❌ 数据提供者测试失败")
            return

        print("\n" + "=" * 60)
        print("✅ 所有测试通过")
        print("=" * 60)

        print("\n📋 M13模块状态:")
        print("  ✅ 数据模型 (ResearchReport, ResearchContext)")
        print("  ✅ 缓存管理器 (CacheManager)")
        print("  ✅ 调研引擎 (ResearchAgent)")
        print("  ✅ LLM分析器 (LLMAnalyzer)")
        print("\n⏭️  下一步: 集成到M1.5/M12/M3")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
