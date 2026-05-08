"""
M13 测试套件运行脚本
"""

import sys
import io
import unittest

# 设置UTF-8编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 导入所有测试模块
from test_research_agent import TestResearchAgent, TestResearchAgentIntegration
from test_llm_analyzer import TestLLMAnalyzer
from test_cache_manager import TestCacheManager
from test_m1_5_integration import TestM1_5_M13Integration
from test_m12_integration import TestM12_M13Integration
from test_m3_integration import TestM3_M13Integration
from test_end_to_end import TestM13EndToEnd


def run_all_tests():
    """运行所有M13测试"""
    print("=" * 80)
    print("M13 Research Agent 测试套件")
    print("=" * 80)
    print()

    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加单元测试
    print("加载单元测试...")
    suite.addTests(loader.loadTestsFromTestCase(TestResearchAgent))
    suite.addTests(loader.loadTestsFromTestCase(TestLLMAnalyzer))
    suite.addTests(loader.loadTestsFromTestCase(TestCacheManager))
    print("  - TestResearchAgent")
    print("  - TestLLMAnalyzer")
    print("  - TestCacheManager")
    print()

    # 添加集成测试
    print("加载集成测试...")
    suite.addTests(loader.loadTestsFromTestCase(TestM1_5_M13Integration))
    suite.addTests(loader.loadTestsFromTestCase(TestM12_M13Integration))
    suite.addTests(loader.loadTestsFromTestCase(TestM3_M13Integration))
    print("  - TestM1_5_M13Integration")
    print("  - TestM12_M13Integration")
    print("  - TestM3_M13Integration")
    print()

    # 添加端到端测试
    print("加载端到端测试...")
    suite.addTests(loader.loadTestsFromTestCase(TestM13EndToEnd))
    print("  - TestM13EndToEnd")
    print()

    # 运行测试
    print("=" * 80)
    print("开始运行测试...")
    print("=" * 80)
    print()

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 输出测试结果摘要
    print()
    print("=" * 80)
    print("测试结果摘要")
    print("=" * 80)
    print(f"总测试数: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")
    print(f"跳过: {len(result.skipped)}")
    print()

    if result.wasSuccessful():
        print("✓ 所有测试通过!")
        return 0
    else:
        print("✗ 部分测试失败")
        return 1


def run_unit_tests_only():
    """只运行单元测试"""
    print("=" * 80)
    print("M13 单元测试")
    print("=" * 80)
    print()

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestResearchAgent))
    suite.addTests(loader.loadTestsFromTestCase(TestLLMAnalyzer))
    suite.addTests(loader.loadTestsFromTestCase(TestCacheManager))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return 0 if result.wasSuccessful() else 1


def run_integration_tests_only():
    """只运行集成测试"""
    print("=" * 80)
    print("M13 集成测试")
    print("=" * 80)
    print()

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestM1_5_M13Integration))
    suite.addTests(loader.loadTestsFromTestCase(TestM12_M13Integration))
    suite.addTests(loader.loadTestsFromTestCase(TestM3_M13Integration))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return 0 if result.wasSuccessful() else 1


def run_e2e_tests_only():
    """只运行端到端测试"""
    print("=" * 80)
    print("M13 端到端测试")
    print("=" * 80)
    print()

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestM13EndToEnd))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='M13 Research Agent 测试套件')
    parser.add_argument(
        '--type',
        choices=['all', 'unit', 'integration', 'e2e'],
        default='all',
        help='测试类型: all(全部), unit(单元测试), integration(集成测试), e2e(端到端测试)'
    )

    args = parser.parse_args()

    if args.type == 'all':
        exit_code = run_all_tests()
    elif args.type == 'unit':
        exit_code = run_unit_tests_only()
    elif args.type == 'integration':
        exit_code = run_integration_tests_only()
    elif args.type == 'e2e':
        exit_code = run_e2e_tests_only()

    sys.exit(exit_code)
