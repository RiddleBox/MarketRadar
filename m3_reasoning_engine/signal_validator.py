"""
M3隐性信号验证模块
基于历史案例验证隐性信号，使用贝叶斯更新置信度
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime


@dataclass
class HistoricalCase:
    """历史案例"""
    case_id: str
    event_type: str  # 事件类型
    event_description: str  # 事件描述
    predicted_outcome: str  # 预测结果
    actual_outcome: str  # 实际结果
    success: bool  # 是否成功
    timeframe: str  # 时间窗口
    confidence_at_prediction: float  # 预测时置信度
    created_at: datetime
    metadata: Dict = None


class CaseLibrary:
    """历史案例库"""

    def __init__(self):
        self.cases: List[HistoricalCase] = []

    def add_case(self, case: HistoricalCase):
        """添加案例"""
        self.cases.append(case)

    def query_similar_cases(
        self,
        signal_type: str,
        keywords: List[str],
        limit: int = 10
    ) -> List[HistoricalCase]:
        """
        查询相似案例

        Args:
            signal_type: 信号类型
            keywords: 关键词列表
            limit: 返回数量限制

        Returns:
            相似案例列表
        """
        matching_cases = []

        for case in self.cases:
            # 类型匹配
            if case.event_type != signal_type:
                continue

            # 关键词匹配
            match_score = 0
            event_text = case.event_description.lower()
            for keyword in keywords:
                if keyword.lower() in event_text:
                    match_score += 1

            if match_score > 0:
                matching_cases.append((case, match_score))

        # 按匹配度排序
        matching_cases.sort(key=lambda x: x[1], reverse=True)

        return [case for case, _ in matching_cases[:limit]]

    def calculate_success_rate(
        self,
        signal_type: str,
        keywords: List[str]
    ) -> float:
        """
        计算历史成功率

        Args:
            signal_type: 信号类型
            keywords: 关键词列表

        Returns:
            成功率 [0-1]
        """
        similar_cases = self.query_similar_cases(signal_type, keywords)

        if not similar_cases:
            return 0.5  # 无历史案例，返回中性概率

        success_count = sum(1 for case in similar_cases if case.success)
        return success_count / len(similar_cases)

    def load_from_dict(self, data: List[Dict]):
        """从字典加载案例"""
        for case_data in data:
            case = HistoricalCase(
                case_id=case_data['case_id'],
                event_type=case_data['event_type'],
                event_description=case_data['event_description'],
                predicted_outcome=case_data['predicted_outcome'],
                actual_outcome=case_data['actual_outcome'],
                success=case_data['success'],
                timeframe=case_data['timeframe'],
                confidence_at_prediction=case_data['confidence_at_prediction'],
                created_at=datetime.fromisoformat(case_data['created_at']),
                metadata=case_data.get('metadata')
            )
            self.add_case(case)

    def to_dict(self) -> List[Dict]:
        """导出为字典"""
        return [
            {
                'case_id': case.case_id,
                'event_type': case.event_type,
                'event_description': case.event_description,
                'predicted_outcome': case.predicted_outcome,
                'actual_outcome': case.actual_outcome,
                'success': case.success,
                'timeframe': case.timeframe,
                'confidence_at_prediction': case.confidence_at_prediction,
                'created_at': case.created_at.isoformat(),
                'metadata': case.metadata
            }
            for case in self.cases
        ]


class ImplicitSignalValidator:
    """隐性信号验证器"""

    def __init__(self, case_library: CaseLibrary):
        """
        初始化验证器

        Args:
            case_library: 历史案例库
        """
        self.case_library = case_library

    def validate(self, implicit_signal) -> float:
        """
        验证隐性信号，返回后验置信度

        Args:
            implicit_signal: ImplicitSignal对象

        Returns:
            后验置信度 [0-1]
        """
        # 1. 提取关键词
        keywords = self._extract_keywords(implicit_signal)

        # 2. 查询相似案例
        similar_cases = self.case_library.query_similar_cases(
            signal_type=implicit_signal.signal_type,
            keywords=keywords,
            limit=10
        )

        if not similar_cases:
            # 无历史案例，返回先验置信度
            return implicit_signal.prior_confidence

        # 3. 计算历史成功率（似然概率）
        success_rate = self.case_library.calculate_success_rate(
            signal_type=implicit_signal.signal_type,
            keywords=keywords
        )

        # 4. 贝叶斯更新
        prior = implicit_signal.prior_confidence  # 先验概率
        likelihood = success_rate  # 似然概率
        posterior = self._bayesian_update(prior, likelihood)

        return posterior

    def _extract_keywords(self, implicit_signal) -> List[str]:
        """提取关键词"""
        keywords = []

        # 从机会描述中提取
        if implicit_signal.opportunity_description:
            # 简单分词（实际应用中可使用jieba等）
            words = implicit_signal.opportunity_description.split()
            keywords.extend(words)

        # 从产业板块中提取
        if implicit_signal.industry_sector:
            keywords.append(implicit_signal.industry_sector)

        # 从推理链中提取
        for link in implicit_signal.reasoning_chain.causal_links:
            keywords.append(link.from_concept)
            keywords.append(link.to_concept)

        return keywords

    def _bayesian_update(self, prior: float, likelihood: float) -> float:
        """
        贝叶斯更新

        Args:
            prior: 先验概率（来自M1.5推理链强度）
            likelihood: 似然概率（来自历史案例成功率）

        Returns:
            后验概率
        """
        # 简化的贝叶斯更新：posterior = prior * likelihood
        # 实际应用中可使用更复杂的贝叶斯公式
        posterior = prior * likelihood

        # 归一化到[0, 1]
        posterior = max(0.0, min(1.0, posterior))

        return posterior

    def batch_validate(self, implicit_signals: List) -> List:
        """
        批量验证隐性信号

        Args:
            implicit_signals: 隐性信号列表

        Returns:
            验证后的信号列表（更新了置信度）
        """
        validated_signals = []

        for signal in implicit_signals:
            # 验证并更新置信度
            posterior_confidence = self.validate(signal)

            # 更新信号的置信度
            # 注意：这里创建新对象而不是修改原对象
            from dataclasses import replace
            validated_signal = replace(
                signal,
                prior_confidence=posterior_confidence
            )

            validated_signals.append(validated_signal)

        return validated_signals

    def filter_by_confidence(
        self,
        signals: List,
        threshold: float = 0.5
    ) -> List:
        """
        按置信度过滤信号

        Args:
            signals: 信号列表
            threshold: 置信度阈值

        Returns:
            过滤后的信号列表
        """
        return [
            signal for signal in signals
            if signal.prior_confidence >= threshold
        ]
