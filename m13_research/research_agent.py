"""
m13_research/research_agent.py — 深度调研引擎

核心职责：
1. 定向信息搜索（研报+新闻+财报）
2. 语义搜索（基于上下文）
3. 多源数据聚合
4. 超时控制和容错处理
5. 缓存管理
"""

import logging
import threading
from typing import Optional, Dict, List
from datetime import datetime

from core.schemas import (
    ResearchReport, ResearchContext, ResearchLevel, ResearchTrigger
)
from integrations.data_provider_manager import DataProviderManager
from m13_research.llm_analyzer import LLMAnalyzer
from m13_research.cache_manager import CacheManager

logger = logging.getLogger(__name__)


class ResearchAgent:
    """深度调研代理"""

    def __init__(
        self,
        data_manager: DataProviderManager,
        llm_analyzer: LLMAnalyzer,
        cache_manager: CacheManager,
        max_concurrent: int = 10
    ):
        """
        初始化调研代理

        Args:
            data_manager: 数据提供者管理器
            llm_analyzer: LLM分析器
            cache_manager: 缓存管理器
            max_concurrent: 最大并发调研数
        """
        self.data_manager = data_manager
        self.llm_analyzer = llm_analyzer
        self.cache_manager = cache_manager
        self.max_concurrent = max_concurrent
        self._semaphore = threading.Semaphore(max_concurrent)

    def quick_research(self, symbol: str, context: str) -> ResearchReport:
        """
        Level 1: 快速验证（< 30秒）

        适用场景：M1.5推理后验证

        Args:
            symbol: 股票代码
            context: 机会上下文

        Returns:
            调研报告
        """
        research_context = ResearchContext(
            symbol=symbol,
            opportunity_context=context,
            research_level=ResearchLevel.QUICK,
            triggered_by=ResearchTrigger.M1_5,
            timeout_seconds=30
        )
        return self._execute_research(research_context)

    def standard_research(self, symbol: str, context: str) -> ResearchReport:
        """
        Level 2: 标准调研（1-2分钟）

        适用场景：M12反向溯源后补充

        Args:
            symbol: 股票代码
            context: 机会上下文

        Returns:
            调研报告
        """
        research_context = ResearchContext(
            symbol=symbol,
            opportunity_context=context,
            research_level=ResearchLevel.STANDARD,
            triggered_by=ResearchTrigger.M12,
            timeout_seconds=120
        )
        return self._execute_research(research_context)

    def deep_research(self, symbol: str, context: str) -> ResearchReport:
        """
        Level 3: 深度调研（3-5分钟）

        适用场景：M3判断后最终验证

        Args:
            symbol: 股票代码
            context: 机会上下文

        Returns:
            调研报告
        """
        research_context = ResearchContext(
            symbol=symbol,
            opportunity_context=context,
            research_level=ResearchLevel.DEEP,
            triggered_by=ResearchTrigger.M3,
            timeout_seconds=300
        )
        return self._execute_research(research_context)

    def _execute_research(self, context: ResearchContext) -> ResearchReport:
        """
        执行调研流程

        Args:
            context: 调研上下文

        Returns:
            调研报告
        """
        # 1. 检查缓存
        cached = self.cache_manager.get(context.symbol, context.research_level.value)
        if cached:
            logger.info(f"[M13] 命中缓存: {context.symbol} ({context.research_level.value})")
            return cached

        # 2. 并发控制
        if not self._semaphore.acquire(blocking=False):
            logger.warning(f"[M13] 调研队列已满，降级跳过: {context.symbol}")
            return self._create_empty_report(context, "调研队列已满")

        try:
            # 3. 收集数据（带超时）
            result = {}
            timeout_event = threading.Event()

            def collect_with_timeout():
                try:
                    result['data'] = self._collect_data(context)
                except Exception as e:
                    result['error'] = str(e)
                finally:
                    timeout_event.set()

            thread = threading.Thread(target=collect_with_timeout)
            thread.daemon = True
            thread.start()

            # 等待超时
            if not timeout_event.wait(timeout=context.timeout_seconds):
                logger.warning(f"[M13] 调研超时: {context.symbol} ({context.timeout_seconds}s)")
                return self._create_timeout_report(context, result.get('data', {}))

            if 'error' in result:
                logger.error(f"[M13] 调研失败: {context.symbol} - {result['error']}")
                return self._create_empty_report(context, result['error'])

            data = result['data']

            # 4. LLM分析
            analysis = self._analyze_data(context, data)

            # 5. 构建报告
            report = ResearchReport(
                symbol=context.symbol,
                research_level=context.research_level,
                triggered_by=context.triggered_by,
                reports=data.get('reports', []),
                news=data.get('news', []),
                fundamentals=data.get('fundamentals', {}),
                quote=data.get('quote', {}),
                semantic_results=data.get('semantic_results', []),
                summary=analysis.get('summary', ''),
                key_findings=analysis.get('key_findings', []),
                risk_factors=analysis.get('risk_factors', []),
                confidence_assessment=analysis.get('confidence_assessment', ''),
                confidence_multiplier=analysis.get('confidence_multiplier', 1.0),
                confidence_delta=analysis.get('confidence_delta', 0.0),
                has_major_negative=analysis.get('has_major_negative', False),
                research_time=datetime.now(),
                data_sources=data.get('sources', []),
                cache_hit=False,
                timeout=False,
                partial_result=data.get('partial', False)
            )

            # 6. 保存缓存
            self.cache_manager.set(report)

            logger.info(
                f"[M13] 调研完成: {context.symbol} ({context.research_level.value}) "
                f"- 置信度调整: {report.confidence_delta:+.2f}"
            )

            return report

        finally:
            self._semaphore.release()

    def _collect_data(self, context: ResearchContext) -> Dict:
        """
        收集原始数据

        Args:
            context: 调研上下文

        Returns:
            数据字典
        """
        data = {
            'reports': [],
            'news': [],
            'fundamentals': {},
            'quote': {},
            'semantic_results': [],
            'sources': [],
            'partial': False
        }

        level = context.research_level

        try:
            # 根据Level决定数据量
            if level == ResearchLevel.QUICK:
                # Level 1: 快速验证
                reports_limit = 5
                news_limit = 10  # 快速验证也需要新闻作为背景
                semantic = False
            elif level == ResearchLevel.STANDARD:
                # Level 2: 标准调研
                reports_limit = 10
                news_limit = 20
                semantic = False
            else:
                # Level 3: 深度调研
                reports_limit = 20
                news_limit = 30
                semantic = True

            # 搜索研报
            if reports_limit > 0:
                try:
                    data['reports'] = self.data_manager.get_research_reports(
                        context.symbol,
                        limit=reports_limit
                    )
                    if data['reports']:
                        data['sources'].append('research_reports')
                except Exception as e:
                    logger.warning(f"搜索研报失败: {e}")
                    data['partial'] = True

            # 搜索新闻
            if news_limit > 0:
                try:
                    data['news'] = self.data_manager.get_news(
                        context.symbol,
                        limit=news_limit
                    )
                    if data['news']:
                        data['sources'].append('news')
                except Exception as e:
                    logger.warning(f"搜索新闻失败: {e}")
                    data['partial'] = True

            # 查询基本面
            try:
                data['fundamentals'] = self.data_manager.get_fundamentals(context.symbol)
                if data['fundamentals']:
                    data['sources'].append('fundamentals')
            except Exception as e:
                logger.warning(f"查询基本面失败: {e}")
                data['partial'] = True

            # 查询行情
            try:
                data['quote'] = self.data_manager.get_quote(context.symbol)
                if data['quote']:
                    data['sources'].append('quote')
            except Exception as e:
                logger.warning(f"查询行情失败: {e}")
                data['partial'] = True

            # 语义搜索（仅Level 3）
            if semantic:
                try:
                    query = self._construct_semantic_query(context)
                    # TODO: 实现语义搜索
                    # data['semantic_results'] = self.data_manager.semantic_search(query)
                    pass
                except Exception as e:
                    logger.warning(f"语义搜索失败: {e}")
                    data['partial'] = True

        except Exception as e:
            logger.error(f"数据收集失败: {e}")
            raise

        return data

    def _analyze_data(self, context: ResearchContext, data: Dict) -> Dict:
        """
        LLM分析数据

        Args:
            context: 调研上下文
            data: 原始数据

        Returns:
            分析结果
        """
        try:
            level = context.research_level

            if level == ResearchLevel.QUICK:
                return self.llm_analyzer.quick_verify(
                    context.opportunity_context,
                    [r.get('title', '') for r in data.get('reports', [])],
                    data.get('fundamentals', {})
                )
            elif level == ResearchLevel.STANDARD:
                return self.llm_analyzer.standard_analyze(
                    context.opportunity_context,
                    data.get('reports', []),
                    data.get('news', []),
                    data.get('fundamentals', {})
                )
            else:
                return self.llm_analyzer.deep_analyze(
                    context.opportunity_context,
                    data.get('reports', []),
                    data.get('news', []),
                    data.get('fundamentals', {}),
                    data.get('semantic_results', [])
                )

        except Exception as e:
            logger.error(f"LLM分析失败: {e}")
            return {
                'summary': f'分析失败: {str(e)}',
                'key_findings': [],
                'risk_factors': [],
                'confidence_multiplier': 1.0,
                'confidence_delta': 0.0,
                'has_major_negative': False
            }

    def _construct_semantic_query(self, context: ResearchContext) -> str:
        """构造语义搜索查询"""
        # TODO: 基于context智能构造查询
        return f"{context.symbol} {context.opportunity_context}"

    def _create_empty_report(self, context: ResearchContext, reason: str) -> ResearchReport:
        """创建空报告"""
        return ResearchReport(
            symbol=context.symbol,
            research_level=context.research_level,
            triggered_by=context.triggered_by,
            summary=f"调研未执行: {reason}",
            research_time=datetime.now(),
            timeout=False,
            partial_result=True
        )

    def _create_timeout_report(self, context: ResearchContext, partial_data: Dict) -> ResearchReport:
        """创建超时报告"""
        return ResearchReport(
            symbol=context.symbol,
            research_level=context.research_level,
            triggered_by=context.triggered_by,
            reports=partial_data.get('reports', []),
            news=partial_data.get('news', []),
            fundamentals=partial_data.get('fundamentals', {}),
            quote=partial_data.get('quote', {}),
            summary="调研超时，返回部分结果",
            research_time=datetime.now(),
            data_sources=partial_data.get('sources', []),
            timeout=True,
            partial_result=True
        )
