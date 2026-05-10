"""
模块健康检查：测试所有13个模块的基本功能
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

print("=" * 80)
print("MarketRadar 模块健康检查")
print("=" * 80)

results = []

# M0: 数据收集器
print("\n[M0] 数据收集器...")
try:
    from m0_collector.unified_collector import UnifiedNewsCollector
    collector = UnifiedNewsCollector()
    print("  [OK] UnifiedNewsCollector 初始化成功")
    results.append(("M0_collector", "OK", "UnifiedNewsCollector可用"))
except Exception as e:
    print(f"  [X] 失败: {e}")
    results.append(("M0_collector", "FAIL", str(e)))

# M1: 信号解码器
print("\n[M1] 信号解码器...")
try:
    from m1_decoder.decoder import SignalDecoder
    from core.llm_client import LLMClient
    decoder = SignalDecoder(llm_client=LLMClient())
    print("  [OK] SignalDecoder 初始化成功")
    results.append(("M1_decoder", "OK", "SignalDecoder可用"))
except Exception as e:
    print(f"  [X] 失败: {e}")
    results.append(("M1_decoder", "FAIL", str(e)))

# M1.5: 隐性信号推理器
print("\n[M1.5] 隐性信号推理器...")
try:
    # ImplicitSignalInferencer是抽象类，检查模块是否可导入
    from m1_5_implicit_reasoner import inferencer
    print("  [OK] ImplicitSignalInferencer 模块可用（抽象类）")
    results.append(("M1.5_implicit_reasoner", "OK", "模块可用（抽象类）"))
except Exception as e:
    print(f"  [X] 失败: {e}")
    results.append(("M1.5_implicit_reasoner", "FAIL", str(e)))

# M2: 信号存储
print("\n[M2] 信号存储...")
try:
    from m2_storage.signal_store import SignalStore
    store = SignalStore()
    # 测试查询
    signals = store.get_by_time_range(
        start=datetime.now() - timedelta(days=1),
        end=datetime.now()
    )
    print(f"  [OK] SignalStore 可用，最近24小时信号数: {len(signals)}")
    results.append(("M2_storage", "OK", f"SignalStore可用，24h信号:{len(signals)}"))
except Exception as e:
    print(f"  [X] 失败: {e}")
    results.append(("M2_storage", "FAIL", str(e)))

# M2: 知识库 (另一个M2?)
print("\n[M2] 知识库...")
try:
    # m2_knowledge_base不存在，跳过
    print("  [SKIP] m2_knowledge_base 目录不存在")
    results.append(("M2_knowledge_base", "SKIP", "目录不存在"))
except Exception as e:
    print(f"  [X] 失败: {e}")
    results.append(("M2_knowledge_base", "FAIL", str(e)))

# M3: 机会判断引擎
print("\n[M3] 机会判断引擎...")
try:
    from m3_judgment.judgment_engine import JudgmentEngine
    engine = JudgmentEngine(llm_client=LLMClient())
    print("  [OK] JudgmentEngine 初始化成功")
    results.append(("M3_judgment", "OK", "JudgmentEngine可用"))
except Exception as e:
    print(f"  [X] 失败: {e}")
    results.append(("M3_judgment", "FAIL", str(e)))

# M3: 推理引擎 (另一个M3?)
print("\n[M3] 推理引擎...")
try:
    # m3_reasoning_engine不存在，跳过
    print("  [SKIP] m3_reasoning_engine 目录不存在")
    results.append(("M3_reasoning_engine", "SKIP", "目录不存在"))
except Exception as e:
    print(f"  [X] 失败: {e}")
    results.append(("M3_reasoning_engine", "FAIL", str(e)))

# M4: 行动设计器
print("\n[M4] 行动设计器...")
try:
    from m4_action.action_designer import ActionDesigner
    designer = ActionDesigner(llm_client=LLMClient())
    print("  [OK] ActionDesigner 初始化成功")
    results.append(("M4_action", "OK", "ActionDesigner可用"))
except Exception as e:
    print(f"  [X] 失败: {e}")
    results.append(("M4_action", "FAIL", str(e)))

# M5: 持仓管理
print("\n[M5] 持仓管理...")
try:
    from m5_position.position_manager import PositionManager
    pm = PositionManager()
    print("  [OK] PositionManager 初始化成功")
    results.append(("M5_position", "OK", "PositionManager可用"))
except Exception as e:
    print(f"  [X] 失败: {e}")
    results.append(("M5_position", "FAIL", str(e)))

# M6: 复盘系统
print("\n[M6] 复盘系统...")
try:
    from m6_retrospective.retrospective import RetrospectiveEngine
    retro = RetrospectiveEngine()
    print("  [OK] RetrospectiveEngine 初始化成功")
    results.append(("M6_retrospective", "OK", "RetrospectiveEngine可用"))
except Exception as e:
    print(f"  [X] 失败: {e}")
    results.append(("M6_retrospective", "FAIL", str(e)))

# M7: 回测器
print("\n[M7] 回测器...")
try:
    from m7_backtester.backtester import Backtester
    backtester = Backtester()
    print("  [OK] Backtester 初始化成功")
    results.append(("M7_backtester", "OK", "Backtester可用"))
except Exception as e:
    print(f"  [X] 失败: {e}")
    results.append(("M7_backtester", "FAIL", str(e)))

# M7: 调度器
print("\n[M7] 调度器...")
try:
    from m7_scheduler.scheduler import Scheduler
    scheduler = Scheduler()
    print("  [OK] Scheduler 初始化成功")
    results.append(("M7_scheduler", "OK", "Scheduler可用"))
except Exception as e:
    print(f"  [X] 失败: {e}")
    results.append(("M7_scheduler", "FAIL", str(e)))

# M8: 知识库
print("\n[M8] 知识库...")
try:
    from m8_knowledge.knowledge_base import KnowledgeBase
    kb8 = KnowledgeBase()
    print("  [OK] KnowledgeBase (M8) 初始化成功")
    results.append(("M8_knowledge", "OK", "KnowledgeBase可用"))
except Exception as e:
    print(f"  [X] 失败: {e}")
    results.append(("M8_knowledge", "FAIL", str(e)))

# M9: 模拟交易器
print("\n[M9] 模拟交易器...")
try:
    from m9_paper_trader.paper_trader import PaperTrader
    trader = PaperTrader()
    positions = trader.list_open()
    print(f"  [OK] PaperTrader 可用，当前持仓: {len(positions)}")
    results.append(("M9_paper_trader", "OK", f"PaperTrader可用，持仓:{len(positions)}"))
except Exception as e:
    print(f"  [X] 失败: {e}")
    results.append(("M9_paper_trader", "FAIL", str(e)))

# M10: 情绪面系统
print("\n[M10] 情绪面系统...")
try:
    from m10_sentiment.sentiment_engine import SentimentEngine
    sentiment = SentimentEngine()
    print("  [OK] SentimentEngine 初始化成功")
    results.append(("M10_sentiment", "OK", "SentimentEngine可用"))
except Exception as e:
    print(f"  [X] 失败: {e}")
    results.append(("M10_sentiment", "FAIL", str(e)))

# M11: Agent模拟
print("\n[M11] Agent模拟...")
try:
    from m11_agent_sim.agent_network import AgentNetwork
    agent_net = AgentNetwork()
    print("  [OK] AgentNetwork 初始化成功")
    results.append(("M11_agent_sim", "OK", "AgentNetwork可用"))
except Exception as e:
    print(f"  [X] 失败: {e}")
    results.append(("M11_agent_sim", "FAIL", str(e)))

# M12: 机会捕捉器
print("\n[M12] 机会捕捉器...")
try:
    from m12_opportunity_catcher.catcher_engine import OpportunityCatcherEngine
    catcher = OpportunityCatcherEngine()
    print("  [OK] OpportunityCatcherEngine 初始化成功")
    results.append(("M12_opportunity_catcher", "OK", "OpportunityCatcherEngine可用"))
except Exception as e:
    print(f"  [X] 失败: {e}")
    results.append(("M12_opportunity_catcher", "FAIL", str(e)))

# M13: 深度调研
print("\n[M13] 深度调研...")
try:
    # ResearchAgent需要依赖注入，只检查模块导入
    from m13_research.research_agent import ResearchAgent
    from m13_research.llm_analyzer import LLMAnalyzer
    from m13_research.cache_manager import CacheManager
    print("  [OK] ResearchAgent 模块可用（需要依赖注入）")
    results.append(("M13_research", "OK", "模块可用（需要依赖注入）"))
except Exception as e:
    print(f"  [X] 失败: {e}")
    results.append(("M13_research", "FAIL", str(e)))

# 汇总报告
print("\n" + "=" * 80)
print("健康检查汇总")
print("=" * 80)

ok_count = sum(1 for _, status, _ in results if status == "OK")
fail_count = sum(1 for _, status, _ in results if status == "FAIL")
skip_count = sum(1 for _, status, _ in results if status == "SKIP")

print(f"\n总计: {len(results)} 个模块")
print(f"  [OK] 正常: {ok_count}")
print(f"  [SKIP] 跳过: {skip_count}")
print(f"  [X] 失败: {fail_count}")

if fail_count > 0:
    print("\n失败模块详情:")
    for module, status, msg in results:
        if status == "FAIL":
            print(f"  - {module}: {msg}")

print("\n所有模块状态:")
for module, status, msg in results:
    if status == "OK":
        status_icon = "[OK]"
    elif status == "SKIP":
        status_icon = "[SKIP]"
    else:
        status_icon = "[X]"
    print(f"  {status_icon} {module:30s} {msg}")

print("\n" + "=" * 80)
print(f"检查完成 - 成功率: {ok_count}/{len(results)} ({ok_count*100//len(results)}%)")
print("=" * 80)
