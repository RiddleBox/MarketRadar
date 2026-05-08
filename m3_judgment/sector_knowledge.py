"""
m3_judgment/sector_knowledge.py - 板块知识库

职责：为M3判断提供板块→龙头股的映射信息
这不是机械映射，而是为LLM提供判断依据
"""

from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class SectorKnowledgeBase:
    """板块知识库

    为M3判断提供板块相关的龙头股信息
    LLM基于这些信息做出判断，而不是机械映射
    """

    def __init__(self):
        # 公司名称→股票代码映射（用于M1直接识别出公司名称的情况）
        self.company_to_code = {}

        # 板块→龙头股映射（静态知识库）
        # 格式：{板块名称: [(股票代码, 公司名称, 核心优势), ...]}
        self.sector_mapping = {
            # 新能源相关
            "新能源": [
                ("601012.SH", "隆基绿能", "全球光伏组件龙头"),
                ("600438.SH", "通威股份", "多晶硅+光伏一体化龙头"),
                ("300274.SZ", "阳光电源", "光伏逆变器+储能龙头"),
                ("688599.SH", "天合光能", "光伏组件龙头"),
                ("002129.SZ", "TCL中环", "硅片龙头"),
            ],
            "光伏": [
                ("601012.SH", "隆基绿能", "全球光伏组件龙头"),
                ("600438.SH", "通威股份", "多晶硅+光伏一体化龙头"),
                ("300274.SZ", "阳光电源", "光伏逆变器龙头"),
                ("688599.SH", "天合光能", "光伏组件龙头"),
                ("002129.SZ", "TCL中环", "硅片龙头"),
            ],
            "储能": [
                ("300274.SZ", "阳光电源", "储能系统龙头"),
                ("300750.SZ", "宁德时代", "动力电池+储能电池龙头"),
                ("002074.SZ", "国轩高科", "储能电池"),
            ],
            "新能源车": [
                ("300750.SZ", "宁德时代", "动力电池绝对龙头"),
                ("002594.SZ", "比亚迪", "新能源车+电池一体化龙头"),
                ("002074.SZ", "国轩高科", "动力电池"),
                ("688005.SH", "容百科技", "正极材料龙头"),
            ],

            # 半导体相关
            "半导体": [
                ("688981.SH", "中芯国际", "晶圆代工龙头"),
                ("603501.SH", "韦尔股份", "CIS芯片龙头"),
                ("688008.SH", "澜起科技", "内存接口芯片龙头"),
                ("002371.SZ", "北方华创", "半导体设备龙头"),
            ],
            "芯片": [
                ("688981.SH", "中芯国际", "晶圆代工龙头"),
                ("603501.SH", "韦尔股份", "CIS芯片龙头"),
                ("688008.SH", "澜起科技", "内存接口芯片龙头"),
            ],

            # 消费相关
            "白酒": [
                ("600519.SH", "贵州茅台", "高端白酒龙头"),
                ("000858.SZ", "五粮液", "高端白酒"),
                ("000568.SZ", "泸州老窖", "次高端白酒龙头"),
            ],
            "医药": [
                ("300760.SZ", "迈瑞医疗", "医疗器械龙头"),
                ("600276.SH", "恒瑞医药", "创新药龙头"),
                ("000661.SZ", "长春高新", "生长激素龙头"),
            ],

            # 金融相关
            "银行": [
                ("601398.SH", "工商银行", "国有大行龙头"),
                ("600036.SH", "招商银行", "股份制银行龙头"),
                ("601166.SH", "兴业银行", "股份制银行"),
            ],
            "券商": [
                ("600030.SH", "中信证券", "券商龙头"),
                ("601688.SH", "华泰证券", "互联网券商龙头"),
                ("600999.SH", "招商证券", "综合券商"),
            ],
            "保险": [
                ("601318.SH", "中国平安", "综合金融龙头"),
                ("601628.SH", "中国人寿", "寿险龙头"),
                ("601601.SH", "中国太保", "综合保险"),
            ],

            # 科技相关
            "人工智能": [
                ("002230.SZ", "科大讯飞", "AI语音龙头"),
                ("603019.SH", "中科曙光", "AI服务器"),
                ("688561.SH", "奇安信", "网络安全+AI"),
            ],
            "云计算": [
                ("002230.SZ", "科大讯飞", "AI+云计算"),
                ("603019.SH", "中科曙光", "云计算基础设施"),
                ("300454.SZ", "深信服", "云计算+网络安全"),
            ],

            # 基建相关
            "建筑": [
                ("601668.SH", "中国建筑", "建筑央企龙头"),
                ("601186.SH", "中国铁建", "基建央企"),
                ("601800.SH", "中国交建", "基建央企"),
            ],
            "水泥": [
                ("600585.SH", "海螺水泥", "水泥行业龙头"),
                ("600801.SH", "华新水泥", "区域水泥龙头"),
            ],
        }

        # 概念→相关板块映射
        self.concept_to_sector = {
            "光伏订单": ["光伏", "新能源"],
            "新能源合作": ["新能源", "光伏", "储能"],
            "芯片国产化": ["半导体", "芯片"],
            "AI应用": ["人工智能", "云计算"],
            "基建投资": ["建筑", "水泥"],
        }

        # 构建公司名称→股票代码的反向映射
        self._build_company_mapping()

    def get_leading_stocks(
        self,
        sectors_or_concepts: List[str],
        top_n: int = 5
    ) -> Dict[str, List[Dict[str, str]]]:
        """获取板块/概念对应的龙头股信息

        Args:
            sectors_or_concepts: 板块或概念名称列表
            top_n: 每个板块返回的龙头股数量

        Returns:
            {
                "板块名称": [
                    {"code": "股票代码", "name": "公司名称", "advantage": "核心优势"},
                    ...
                ]
            }
        """
        result = {}

        for item in sectors_or_concepts:
            # 1. 直接匹配板块
            if item in self.sector_mapping:
                stocks = self.sector_mapping[item][:top_n]
                result[item] = [
                    {"code": code, "name": name, "advantage": advantage}
                    for code, name, advantage in stocks
                ]

            # 2. 概念→板块映射
            elif item in self.concept_to_sector:
                related_sectors = self.concept_to_sector[item]
                for sector in related_sectors:
                    if sector in self.sector_mapping:
                        stocks = self.sector_mapping[sector][:top_n]
                        result[f"{item}({sector})"] = [
                            {"code": code, "name": name, "advantage": advantage}
                            for code, name, advantage in stocks
                        ]

            # 3. 模糊匹配（包含关系）
            else:
                matched = False
                for sector_name, stocks in self.sector_mapping.items():
                    if item in sector_name or sector_name in item:
                        result[f"{item}→{sector_name}"] = [
                            {"code": code, "name": name, "advantage": advantage}
                            for code, name, advantage in stocks[:top_n]
                        ]
                        matched = True
                        break

                if not matched:
                    logger.warning(f"未找到板块/概念的映射: {item}")

        return result

    def format_for_prompt(self, sector_stocks_info: Dict[str, List[Dict[str, str]]]) -> str:
        """将板块股票信息格式化为prompt文本

        Args:
            sector_stocks_info: get_leading_stocks()的返回值

        Returns:
            格式化的文本，用于注入M3的prompt
        """
        if not sector_stocks_info:
            return ""

        lines = ["## 相关板块的龙头股票信息"]
        lines.append("（供判断时参考，请根据机会论点选择最相关的标的）")
        lines.append("")

        for sector, stocks in sector_stocks_info.items():
            lines.append(f"### {sector}")
            for stock in stocks:
                lines.append(
                    f"- {stock['name']}({stock['code']}): {stock['advantage']}"
                )
            lines.append("")

        return "\n".join(lines)

    def is_stock_code(self, instrument: str) -> bool:
        """判断是否是股票代码格式

        Args:
            instrument: 标的字符串

        Returns:
            True if 是股票代码格式
        """
        import re
        # 匹配格式：6位数字.SH/SZ/HK 或 纯数字（美股）
        return bool(re.match(r'^\d{6}\.(SH|SZ|HK)$', instrument)) or \
               bool(re.match(r'^\d{4,6}\.HK$', instrument)) or \
               bool(re.match(r'^[A-Z]{1,5}$', instrument))  # 美股ticker

    def extract_sectors_from_signals(self, signals: List) -> List[str]:
        """从信号列表中提取板块/概念名称

        Args:
            signals: MarketSignal列表

        Returns:
            板块/概念名称列表（去重）
        """
        sectors = set()

        for signal in signals:
            # 从affected_instruments提取
            for inst in signal.affected_instruments:
                if not self.is_stock_code(inst):
                    sectors.add(inst)

            # 从signal_label提取（可能包含板块名称）
            label = signal.signal_label
            for sector_name in self.sector_mapping.keys():
                if sector_name in label:
                    sectors.add(sector_name)

            # 从tags提取（如果存在）
            if hasattr(signal, 'tags') and signal.tags:
                for tag in signal.tags:
                    if tag.startswith("sector:"):
                        sector = tag.replace("sector:", "")
                        sectors.add(sector)

        return list(sectors)

    def _build_company_mapping(self):
        """构建公司名称→股票代码的反向映射"""
        for sector, stocks in self.sector_mapping.items():
            for code, name, advantage in stocks:
                # 完整公司名称
                self.company_to_code[name] = code

                # 简称（去掉"股份"、"集团"等后缀）
                short_name = name.replace("股份", "").replace("集团", "").replace("有限公司", "").replace("科技", "")
                if short_name != name:
                    self.company_to_code[short_name] = code

    def resolve_instruments(self, instruments: List[str]) -> List[str]:
        """将混合的标的列表（可能包含股票代码、公司名称、板块名称）统一转换为股票代码

        Args:
            instruments: 混合的标的列表

        Returns:
            股票代码列表（去重）
        """
        result_codes = set()

        for inst in instruments:
            # 1. 已经是股票代码，直接保留
            if self.is_stock_code(inst):
                result_codes.add(inst)

            # 2. 是公司名称，映射到股票代码
            elif inst in self.company_to_code:
                result_codes.add(self.company_to_code[inst])

            # 3. 是板块名称，映射到龙头股
            elif inst in self.sector_mapping:
                stocks = self.sector_mapping[inst][:3]  # 取前3个龙头
                for code, name, advantage in stocks:
                    result_codes.add(code)

            # 4. 模糊匹配公司名称（部分匹配）
            else:
                matched = False
                for company_name, code in self.company_to_code.items():
                    if inst in company_name or company_name in inst:
                        result_codes.add(code)
                        matched = True
                        break

                # 5. 模糊匹配板块名称
                if not matched:
                    for sector_name, stocks in self.sector_mapping.items():
                        if inst in sector_name or sector_name in inst:
                            for code, name, advantage in stocks[:3]:
                                result_codes.add(code)
                            break

        return list(result_codes)


# 便捷函数
def get_sector_knowledge() -> SectorKnowledgeBase:
    """获取板块知识库单例"""
    return SectorKnowledgeBase()
