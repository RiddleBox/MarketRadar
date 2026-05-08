"""
m13_research/llm_analyzer.py — LLM分析器

核心职责：
1. 构建不同Level的Prompt
2. 调用LLM进行分析
3. 解析JSON格式输出
4. 超时和容错处理
"""

import json
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class LLMAnalyzer:
    """LLM分析器"""

    def __init__(self, llm_client):
        """
        初始化LLM分析器

        Args:
            llm_client: LLM客户端（支持chat方法）
        """
        self.llm_client = llm_client

    def quick_verify(
        self,
        context: str,
        report_titles: List[str],
        fundamentals: Dict
    ) -> Dict:
        """
        快速验证分析（Level 1）

        Args:
            context: 机会上下文
            report_titles: 研报标题列表
            fundamentals: 基本面数据

        Returns:
            分析结果
        """
        prompt = self._build_quick_prompt(context, report_titles, fundamentals)

        try:
            result = self.llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            return self._parse_quick_result(result)
        except Exception as e:
            logger.error(f"快速验证失败: {e}")
            return self._default_result()

    def standard_analyze(
        self,
        context: str,
        reports: List[Dict],
        news: List[Dict],
        fundamentals: Dict
    ) -> Dict:
        """
        标准分析（Level 2）

        Args:
            context: 机会上下文
            reports: 研报列表
            news: 新闻列表
            fundamentals: 基本面数据

        Returns:
            分析结果
        """
        prompt = self._build_standard_prompt(context, reports, news, fundamentals)

        try:
            result = self.llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1500,
                response_format={"type": "json_object"}
            )
            return self._parse_standard_result(result)
        except Exception as e:
            logger.error(f"标准分析失败: {e}")
            return self._default_result()

    def deep_analyze(
        self,
        context: str,
        reports: List[Dict],
        news: List[Dict],
        fundamentals: Dict,
        semantic_results: List[Dict]
    ) -> Dict:
        """
        深度分析（Level 3）

        Args:
            context: 机会上下文
            reports: 研报列表
            news: 新闻列表
            fundamentals: 基本面数据
            semantic_results: 语义搜索结果

        Returns:
            分析结果
        """
        prompt = self._build_deep_prompt(
            context, reports, news, fundamentals, semantic_results
        )

        try:
            result = self.llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2500,
                response_format={"type": "json_object"}
            )
            return self._parse_deep_result(result)
        except Exception as e:
            logger.error(f"深度分析失败: {e}")
            return self._default_result()

    def _build_quick_prompt(
        self,
        context: str,
        report_titles: List[str],
        fundamentals: Dict
    ) -> str:
        """构建快速验证Prompt"""
        titles_text = "\n".join([f"- {t}" for t in report_titles[:5]]) if report_titles else "（无研报）"

        pe = fundamentals.get('pe_ttm', fundamentals.get('pe', 'N/A'))
        pb = fundamentals.get('pb', 'N/A')
        roe = fundamentals.get('roe', 'N/A')

        return f"""你是一个专业的投资分析师。请快速验证以下推理是否合理：

【推理】
{context}

【研报标题】（最近5篇）
{titles_text}

【基本面】
PE: {pe}, PB: {pb}, ROE: {roe}%

请在30秒内回答：
1. 推理逻辑是否成立？（是/否/部分成立）
2. 是否有明显反向证据？（是/否）
3. 置信度调整建议（0.5-2.0倍）

输出JSON格式：
{{
    "logic_valid": "是/否/部分成立",
    "has_counter_evidence": false,
    "confidence_multiplier": 1.0,
    "summary": "简短说明（50字内）"
}}"""

    def _build_standard_prompt(
        self,
        context: str,
        reports: List[Dict],
        news: List[Dict],
        fundamentals: Dict
    ) -> str:
        """构建标准分析Prompt"""
        # 研报摘要
        reports_text = ""
        for i, r in enumerate(reports[:10], 1):
            title = r.get('title', '')
            rating = r.get('rating', '')
            institution = r.get('institution', '')
            reports_text += f"{i}. {title} - {institution} ({rating})\n"

        if not reports_text:
            reports_text = "（无研报）"

        # 新闻摘要
        news_text = ""
        for i, n in enumerate(news[:10], 1):
            title = n.get('title', '')
            source = n.get('source', '')
            news_text += f"{i}. [{source}] {title}\n"

        if not news_text:
            news_text = "（无新闻）"

        return f"""你是一个专业的投资分析师。请综合分析以下信息：

【机会描述】
{context}

【研报摘要】（最近10篇）
{reports_text}

【相关新闻】（最近10条）
{news_text}

【基本面数据】
{json.dumps(fundamentals, ensure_ascii=False, indent=2)}

请分析：
1. 关键发现（3-5条，每条50字内）
2. 风险因素（2-3条，每条50字内）
3. 置信度调整（-0.3 ~ +0.3）
4. 综合摘要（200字内）

输出JSON格式：
{{
    "key_findings": ["发现1", "发现2", "发现3"],
    "risk_factors": ["风险1", "风险2"],
    "confidence_delta": 0.0,
    "summary": "综合摘要"
}}"""

    def _build_deep_prompt(
        self,
        context: str,
        reports: List[Dict],
        news: List[Dict],
        fundamentals: Dict,
        semantic_results: List[Dict]
    ) -> str:
        """构建深度分析Prompt"""
        # 研报详细分析
        reports_text = ""
        for i, r in enumerate(reports[:20], 1):
            title = r.get('title', '')
            rating = r.get('rating', '')
            institution = r.get('institution', '')
            eps_cur = r.get('eps_cur', '')
            eps_next = r.get('eps_next', '')
            reports_text += f"{i}. {title}\n   机构: {institution}, 评级: {rating}\n"
            if eps_cur:
                reports_text += f"   EPS预测: 今年{eps_cur}, 明年{eps_next}\n"

        if not reports_text:
            reports_text = "（无研报）"

        # 新闻分析
        news_text = ""
        for i, n in enumerate(news[:20], 1):
            title = n.get('title', '')
            source = n.get('source', '')
            published = n.get('published_at', '')
            news_text += f"{i}. [{source}] {title} ({published})\n"

        if not news_text:
            news_text = "（无新闻）"

        # 语义搜索结果
        semantic_text = ""
        for i, s in enumerate(semantic_results[:10], 1):
            title = s.get('title', '')
            semantic_text += f"{i}. {title}\n"

        if not semantic_text:
            semantic_text = "（无语义搜索结果）"

        return f"""你是一个资深投资分析师。请对以下机会进行最终验证：

【机会描述】
{context}

【研报分析】（最近20篇）
{reports_text}

【新闻分析】（最近20条）
{news_text}

【基本面数据】
{json.dumps(fundamentals, ensure_ascii=False, indent=2)}

【行业趋势】（语义搜索结果）
{semantic_text}

请深度分析：
1. 关键发现（5条，每条100字内）
2. 风险因素（3条，每条100字内）
3. 是否发现重大利空？（true/false）
4. 置信度评估说明（200字）
5. 置信度调整（-0.3 ~ +0.3）
6. 综合摘要（300字内）

输出JSON格式：
{{
    "key_findings": ["发现1", "发现2", "发现3", "发现4", "发现5"],
    "risk_factors": ["风险1", "风险2", "风险3"],
    "has_major_negative": false,
    "confidence_assessment": "置信度评估说明",
    "confidence_delta": 0.0,
    "summary": "综合摘要"
}}"""

    def _parse_quick_result(self, result: str) -> Dict:
        """解析快速验证结果"""
        try:
            data = json.loads(result)
            return {
                'summary': data.get('summary', ''),
                'confidence_multiplier': float(data.get('confidence_multiplier', 1.0)),
                'confidence_delta': 0.0,
                'key_findings': [],
                'risk_factors': [],
                'has_major_negative': data.get('has_counter_evidence', False)
            }
        except Exception as e:
            logger.error(f"解析快速验证结果失败: {e}")
            return self._default_result()

    def _parse_standard_result(self, result: str) -> Dict:
        """解析标准分析结果"""
        try:
            data = json.loads(result)
            return {
                'summary': data.get('summary', ''),
                'key_findings': data.get('key_findings', []),
                'risk_factors': data.get('risk_factors', []),
                'confidence_delta': float(data.get('confidence_delta', 0.0)),
                'confidence_multiplier': 1.0,
                'confidence_assessment': '',
                'has_major_negative': False
            }
        except Exception as e:
            logger.error(f"解析标准分析结果失败: {e}")
            return self._default_result()

    def _parse_deep_result(self, result: str) -> Dict:
        """解析深度分析结果"""
        try:
            data = json.loads(result)
            return {
                'summary': data.get('summary', ''),
                'key_findings': data.get('key_findings', []),
                'risk_factors': data.get('risk_factors', []),
                'confidence_assessment': data.get('confidence_assessment', ''),
                'confidence_delta': float(data.get('confidence_delta', 0.0)),
                'confidence_multiplier': 1.0,
                'has_major_negative': data.get('has_major_negative', False)
            }
        except Exception as e:
            logger.error(f"解析深度分析结果失败: {e}")
            return self._default_result()

    def _default_result(self) -> Dict:
        """默认结果（分析失败时）"""
        return {
            'summary': '分析失败，信息不足',
            'key_findings': [],
            'risk_factors': [],
            'confidence_assessment': '',
            'confidence_multiplier': 1.0,
            'confidence_delta': 0.0,
            'has_major_negative': False
        }
