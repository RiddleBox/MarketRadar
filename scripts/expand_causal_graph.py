#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
因果图谱扩充脚本
从10个货币政策模式扩展到50+模式
"""
import sys
import os
from pathlib import Path

# Windows控制台UTF-8编码
if sys.platform == 'win32':
    os.system('chcp 65001 > nul')
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent.parent))

from m2_storage.causal_graph import CausalGraphManager

def add_industry_policy_patterns(manager: CausalGraphManager):
    """行业政策类模式（10个）"""
    patterns = [
        {
            "pattern_id": "industry_subsidy",
            "name": "行业补贴政策",
            "trigger_conditions": ["政府发布行业补贴政策", "新能源/芯片/生物医药等战略行业"],
            "causal_chain": ["政策发布 → 降低企业成本 → 提升盈利预期 → 板块估值上修"],
            "expected_outcomes": ["相关板块短期上涨5-15%", "龙头企业受益最明显"],
            "time_lag": "1-5个交易日",
            "confidence": 0.75
        },
        {
            "pattern_id": "industry_regulation",
            "name": "行业监管收紧",
            "trigger_conditions": ["监管部门发布限制性政策", "教育/互联网/地产等行业"],
            "causal_chain": ["政策发布 → 业务受限 → 盈利预期下调 → 板块估值下修"],
            "expected_outcomes": ["相关板块短期下跌10-30%", "持续压制估值"],
            "time_lag": "即时反应",
            "confidence": 0.85
        },
        {
            "pattern_id": "carbon_neutral",
            "name": "碳中和政策",
            "trigger_conditions": ["碳排放配额收紧", "新能源替代政策"],
            "causal_chain": ["政策推进 → 传统能源成本上升 → 新能源竞争力提升 → 板块轮动"],
            "expected_outcomes": ["煤炭/石油板块承压", "光伏/风电/储能板块受益"],
            "time_lag": "3-10个交易日",
            "confidence": 0.70
        },
        {
            "pattern_id": "medical_reform",
            "name": "医保集采政策",
            "trigger_conditions": ["新一轮集采名单公布", "药品/医疗器械降价"],
            "causal_chain": ["集采落地 → 产品价格下降 → 利润率压缩 → 相关公司估值下调"],
            "expected_outcomes": ["被集采企业短期下跌5-20%", "创新药企业相对受益"],
            "time_lag": "1-3个交易日",
            "confidence": 0.80
        },
        {
            "pattern_id": "digital_economy",
            "name": "数字经济政策",
            "trigger_conditions": ["数字基建投资计划", "数据要素市场化政策"],
            "causal_chain": ["政策支持 → 行业投资加速 → 订单预期改善 → 板块估值提升"],
            "expected_outcomes": ["云计算/大数据/AI板块上涨", "龙头企业受益"],
            "time_lag": "2-7个交易日",
            "confidence": 0.70
        },
        {
            "pattern_id": "real_estate_easing",
            "name": "地产政策放松",
            "trigger_conditions": ["限购放松", "房贷利率下调", "保交楼政策"],
            "causal_chain": ["政策宽松 → 购房需求释放 → 销售预期改善 → 地产链估值修复"],
            "expected_outcomes": ["地产/建材/家电板块反弹", "优质房企受益"],
            "time_lag": "1-5个交易日",
            "confidence": 0.75
        },
        {
            "pattern_id": "export_control",
            "name": "出口管制政策",
            "trigger_conditions": ["关键技术/产品出口限制", "地缘政治因素"],
            "causal_chain": ["管制加强 → 海外订单受阻 → 业绩预期下调 → 相关公司承压"],
            "expected_outcomes": ["出口依赖型企业下跌", "国产替代概念受益"],
            "time_lag": "即时反应",
            "confidence": 0.80
        },
        {
            "pattern_id": "consumption_stimulus",
            "name": "消费刺激政策",
            "trigger_conditions": ["消费券发放", "家电/汽车以旧换新补贴"],
            "causal_chain": ["补贴政策 → 消费需求提振 → 销售增长 → 消费板块估值提升"],
            "expected_outcomes": ["家电/汽车/零售板块上涨", "龙头品牌受益"],
            "time_lag": "3-10个交易日",
            "confidence": 0.70
        },
        {
            "pattern_id": "tech_breakthrough",
            "name": "科技突破支持政策",
            "trigger_conditions": ["国家重大科技专项", "关键技术攻关支持"],
            "causal_chain": ["政策支持 → 研发投入增加 → 技术突破预期 → 科技板块估值提升"],
            "expected_outcomes": ["半导体/AI/生物科技板块上涨", "技术领先企业受益"],
            "time_lag": "5-15个交易日",
            "confidence": 0.65
        },
        {
            "pattern_id": "agriculture_support",
            "name": "农业支持政策",
            "trigger_conditions": ["粮食安全政策", "种业振兴", "农业补贴"],
            "causal_chain": ["政策支持 → 农业投资增加 → 行业景气度提升 → 农业板块估值修复"],
            "expected_outcomes": ["种业/农机/化肥板块上涨", "龙头企业受益"],
            "time_lag": "3-10个交易日",
            "confidence": 0.70
        }
    ]
    
    for p in patterns:
        manager.add_pattern(**p)
    print(f"[OK] 添加 {len(patterns)} 个行业政策模式")

def add_company_event_patterns(manager: CausalGraphManager):
    """个股事件类模式（10个）"""
    patterns = [
        {
            "pattern_id": "earnings_beat",
            "name": "业绩超预期",
            "trigger_conditions": ["季报/年报净利润增速超市场预期20%+", "业绩指引上调"],
            "causal_chain": ["业绩公布 → 盈利预期上修 → 估值重估 → 股价上涨"],
            "expected_outcomes": ["个股短期上涨10-30%", "带动板块情绪"],
            "time_lag": "1-3个交易日",
            "confidence": 0.85
        },
        {
            "pattern_id": "earnings_miss",
            "name": "业绩低于预期",
            "trigger_conditions": ["季报/年报净利润低于预期30%+", "业绩预警"],
            "causal_chain": ["业绩公布 → 盈利预期下调 → 估值下修 → 股价下跌"],
            "expected_outcomes": ["个股短期下跌15-40%", "可能连续跌停"],
            "time_lag": "即时反应",
            "confidence": 0.90
        },
        {
            "pattern_id": "major_contract",
            "name": "重大合同签订",
            "trigger_conditions": ["签订大额订单（>年营收20%）", "战略合作协议"],
            "causal_chain": ["合同公告 → 订单可见性提升 → 业绩确定性增强 → 估值提升"],
            "expected_outcomes": ["个股短期上涨5-15%", "持续性看合同执行"],
            "time_lag": "1-2个交易日",
            "confidence": 0.75
        },
        {
            "pattern_id": "product_launch",
            "name": "重磅产品发布",
            "trigger_conditions": ["新产品上市", "技术突破", "市场空间大"],
            "causal_chain": ["产品发布 → 市场空间打开 → 成长预期提升 → 估值扩张"],
            "expected_outcomes": ["个股中期上涨20-50%", "需验证销售数据"],
            "time_lag": "3-10个交易日",
            "confidence": 0.70
        },
        {
            "pattern_id": "management_change",
            "name": "核心高管变动",
            "trigger_conditions": ["董事长/总经理离职", "核心团队变动"],
            "causal_chain": ["高管变动 → 战略不确定性 → 市场信心下降 → 股价承压"],
            "expected_outcomes": ["个股短期下跌5-15%", "需观察新管理层"],
            "time_lag": "1-3个交易日",
            "confidence": 0.70
        },
        {
            "pattern_id": "asset_restructuring",
            "name": "资产重组",
            "trigger_conditions": ["并购重组预案", "资产注入", "业务剥离"],
            "causal_chain": ["重组公告 → 资产质量改善预期 → 估值重估 → 股价波动"],
            "expected_outcomes": ["停牌前炒作", "复牌后看方案质量"],
            "time_lag": "即时反应",
            "confidence": 0.65
        },
        {
            "pattern_id": "dividend_increase",
            "name": "高分红预案",
            "trigger_conditions": ["分红率>50%", "股息率>5%", "连续高分红"],
            "causal_chain": ["分红预案 → 现金流稳定信号 → 价值投资者买入 → 股价稳定上涨"],
            "expected_outcomes": ["个股稳健上涨5-10%", "吸引长线资金"],
            "time_lag": "3-10个交易日",
            "confidence": 0.75
        },
        {
            "pattern_id": "share_buyback",
            "name": "股份回购",
            "trigger_conditions": ["公司公告回购计划", "回购金额>市值1%"],
            "causal_chain": ["回购公告 → 管理层看好信号 → 市场信心提升 → 股价支撑"],
            "expected_outcomes": ["个股短期上涨3-8%", "提供下跌保护"],
            "time_lag": "1-5个交易日",
            "confidence": 0.70
        },
        {
            "pattern_id": "insider_trading",
            "name": "高管增持/减持",
            "trigger_conditions": ["董监高大额增持/减持", "金额>1000万"],
            "causal_chain": ["增持→看好信号→股价上涨 / 减持→看空信号→股价下跌"],
            "expected_outcomes": ["增持后上涨5-10%", "减持后下跌3-8%"],
            "time_lag": "1-3个交易日",
            "confidence": 0.75
        },
        {
            "pattern_id": "litigation_risk",
            "name": "重大诉讼/处罚",
            "trigger_conditions": ["涉及金额>净资产10%", "监管处罚", "刑事调查"],
            "causal_chain": ["诉讼公告 → 或有负债增加 → 不确定性上升 → 股价下跌"],
            "expected_outcomes": ["个股短期下跌10-30%", "可能ST风险"],
            "time_lag": "即时反应",
            "confidence": 0.85
        }
    ]
    
    for p in patterns:
        manager.add_pattern(**p)
    print(f"[OK] 添加 {len(patterns)} 个个股事件模式")

def add_technical_patterns(manager: CausalGraphManager):
    """技术面类模式（10个）"""
    patterns = [
        {
            "pattern_id": "breakout_resistance",
            "name": "突破关键阻力位",
            "trigger_conditions": ["放量突破前高", "成交量>5日均量2倍", "收盘站稳阻力位"],
            "causal_chain": ["突破阻力 → 技术形态改善 → 趋势跟随者入场 → 加速上涨"],
            "expected_outcomes": ["短期继续上涨5-15%", "需确认不是假突破"],
            "time_lag": "1-3个交易日",
            "confidence": 0.70
        },
        {
            "pattern_id": "breakdown_support",
            "name": "跌破关键支撑位",
            "trigger_conditions": ["放量跌破前低", "收盘跌破支撑位", "技术形态破坏"],
            "causal_chain": ["跌破支撑 → 止损盘涌出 → 恐慌情绪蔓延 → 加速下跌"],
            "expected_outcomes": ["短期继续下跌10-20%", "寻找下一支撑位"],
            "time_lag": "1-3个交易日",
            "confidence": 0.75
        },
        {
            "pattern_id": "golden_cross",
            "name": "金叉信号",
            "trigger_conditions": ["短期均线上穿长期均线", "如5日线上穿20日线"],
            "causal_chain": ["均线金叉 → 趋势转多信号 → 技术派买入 → 股价上涨"],
            "expected_outcomes": ["中期上涨趋势", "需结合成交量确认"],
            "time_lag": "3-10个交易日",
            "confidence": 0.65
        },
        {
            "pattern_id": "death_cross",
            "name": "死叉信号",
            "trigger_conditions": ["短期均线下穿长期均线", "如5日线下穿20日线"],
            "causal_chain": ["均线死叉 → 趋势转空信号 → 技术派卖出 → 股价下跌"],
            "expected_outcomes": ["中期下跌趋势", "需结合成交量确认"],
            "time_lag": "3-10个交易日",
            "confidence": 0.65
        },
        {
            "pattern_id": "volume_surge",
            "name": "异常放量",
            "trigger_conditions": ["成交量>20日均量5倍", "无明显利好/利空"],
            "causal_chain": ["异常放量 → 主力资金异动 → 可能变盘 → 密切关注"],
            "expected_outcomes": ["短期波动加剧", "方向不确定"],
            "time_lag": "1-3个交易日",
            "confidence": 0.60
        },
        {
            "pattern_id": "rsi_oversold",
            "name": "RSI超卖",
            "trigger_conditions": ["RSI<20", "连续下跌", "基本面无重大利空"],
            "causal_chain": ["超卖信号 → 技术性反弹预期 → 抄底资金入场 → 短期反弹"],
            "expected_outcomes": ["短期反弹5-10%", "不代表趋势反转"],
            "time_lag": "1-5个交易日",
            "confidence": 0.70
        },
        {
            "pattern_id": "rsi_overbought",
            "name": "RSI超买",
            "trigger_conditions": ["RSI>80", "连续上涨", "估值偏高"],
            "causal_chain": ["超买信号 → 获利盘兑现 → 短期回调 → 股价调整"],
            "expected_outcomes": ["短期回调5-15%", "不代表趋势反转"],
            "time_lag": "1-5个交易日",
            "confidence": 0.70
        },
        {
            "pattern_id": "macd_divergence",
            "name": "MACD背离",
            "trigger_conditions": ["股价创新高但MACD不创新高（顶背离）", "或相反（底背离）"],
            "causal_chain": ["背离信号 → 趋势动能衰竭 → 可能反转 → 股价转向"],
            "expected_outcomes": ["顶背离后下跌", "底背离后上涨"],
            "time_lag": "3-10个交易日",
            "confidence": 0.65
        },
        {
            "pattern_id": "gap_up",
            "name": "向上跳空缺口",
            "trigger_conditions": ["开盘价>前日最高价", "有重大利好", "成交量放大"],
            "causal_chain": ["跳空高开 → 多头力量强 → 惜售情绪 → 继续上涨"],
            "expected_outcomes": ["短期上涨5-15%", "缺口可能回补"],
            "time_lag": "1-3个交易日",
            "confidence": 0.70
        },
        {
            "pattern_id": "gap_down",
            "name": "向下跳空缺口",
            "trigger_conditions": ["开盘价<前日最低价", "有重大利空", "成交量放大"],
            "causal_chain": ["跳空低开 → 空头力量强 → 恐慌抛售 → 继续下跌"],
            "expected_outcomes": ["短期下跌10-20%", "缺口可能回补"],
            "time_lag": "1-3个交易日",
            "confidence": 0.75
        }
    ]
    
    for p in patterns:
        manager.add_pattern(**p)
    print(f"[OK] 添加 {len(patterns)} 个技术面模式")

def add_capital_flow_patterns(manager: CausalGraphManager):
    """资金面类模式（10个）"""
    patterns = [
        {
            "pattern_id": "northbound_inflow",
            "name": "北向资金大幅流入",
            "trigger_conditions": ["单日净流入>100亿", "连续3日净流入"],
            "causal_chain": ["外资流入 → 市场信心提升 → 蓝筹股受益 → 指数上涨"],
            "expected_outcomes": ["大盘稳定上涨", "白马股领涨"],
            "time_lag": "1-3个交易日",
            "confidence": 0.80
        },
        {
            "pattern_id": "northbound_outflow",
            "name": "北向资金大幅流出",
            "trigger_conditions": ["单日净流出>100亿", "连续3日净流出"],
            "causal_chain": ["外资流出 → 市场信心下降 → 蓝筹股承压 → 指数下跌"],
            "expected_outcomes": ["大盘调整", "白马股领跌"],
            "time_lag": "1-3个交易日",
            "confidence": 0.80
        },
        {
            "pattern_id": "margin_surge",
            "name": "融资余额快速上升",
            "trigger_conditions": ["融资余额单周增长>5%", "融资买入占比>15%"],
            "causal_chain": ["杠杆资金入场 → 做多情绪高涨 → 短期推升股价 → 波动加剧"],
            "expected_outcomes": ["短期上涨加速", "回调风险增加"],
            "time_lag": "3-7个交易日",
            "confidence": 0.70
        },
        {
            "pattern_id": "margin_decline",
            "name": "融资余额快速下降",
            "trigger_conditions": ["融资余额单周下降>5%", "融资偿还加速"],
            "causal_chain": ["杠杆资金撤离 → 做多情绪降温 → 股价承压 → 下跌加速"],
            "expected_outcomes": ["短期下跌加速", "去杠杆压力"],
            "time_lag": "3-7个交易日",
            "confidence": 0.75
        },
        {
            "pattern_id": "institutional_buying",
            "name": "机构大幅加仓",
            "trigger_conditions": ["基金/社保/险资持仓环比增加>20%", "龙虎榜机构席位"],
            "causal_chain": ["机构买入 → 长线资金入场 → 估值支撑 → 股价稳定上涨"],
            "expected_outcomes": ["中长期上涨", "波动率降低"],
            "time_lag": "5-15个交易日",
            "confidence": 0.75
        },
        {
            "pattern_id": "institutional_selling",
            "name": "机构大幅减仓",
            "trigger_conditions": ["基金/社保/险资持仓环比减少>20%", "龙虎榜机构卖出"],
            "causal_chain": ["机构卖出 → 长线资金撤离 → 估值支撑减弱 → 股价承压"],
            "expected_outcomes": ["中长期下跌", "流动性变差"],
            "time_lag": "5-15个交易日",
            "confidence": 0.75
        },
        {
            "pattern_id": "hot_money_speculation",
            "name": "游资炒作",
            "trigger_conditions": ["龙虎榜游资席位集中", "换手率>20%", "短期暴涨"],
            "causal_chain": ["游资接力 → 题材炒作 → 短期暴涨 → 高位出货"],
            "expected_outcomes": ["短期暴涨暴跌", "高风险高收益"],
            "time_lag": "1-5个交易日",
            "confidence": 0.60
        },
        {
            "pattern_id": "etf_inflow",
            "name": "ETF大额申购",
            "trigger_conditions": ["行业/主题ETF单日申购>10亿", "连续净申购"],
            "causal_chain": ["ETF申购 → 被动配置需求 → 成分股买盘 → 板块上涨"],
            "expected_outcomes": ["相关板块上涨", "龙头股受益"],
            "time_lag": "1-3个交易日",
            "confidence": 0.75
        },
        {
            "pattern_id": "etf_outflow",
            "name": "ETF大额赎回",
            "trigger_conditions": ["行业/主题ETF单日赎回>10亿", "连续净赎回"],
            "causal_chain": ["ETF赎回 → 被动卖出压力 → 成分股承压 → 板块下跌"],
            "expected_outcomes": ["相关板块下跌", "龙头股承压"],
            "time_lag": "1-3个交易日",
            "confidence": 0.75
        },
        {
            "pattern_id": "block_trade",
            "name": "大宗交易异常",
            "trigger_conditions": ["大宗交易折价>5%", "成交额>流通市值1%"],
            "causal_chain": ["大宗折价 → 大股东/机构减持 → 市场信心受挫 → 股价承压"],
            "expected_outcomes": ["短期下跌5-10%", "需观察后续"],
            "time_lag": "1-3个交易日",
            "confidence": 0.70
        }
    ]
    
    for p in patterns:
        manager.add_pattern(**p)
    print(f"[OK] 添加 {len(patterns)} 个资金面模式")

def main():
    manager = CausalGraphManager()
    
    print("开始扩充因果图谱...")
    print(f"当前模式数量: {len(manager.list_patterns())}")
    
    add_industry_policy_patterns(manager)
    add_company_event_patterns(manager)
    add_technical_patterns(manager)
    add_capital_flow_patterns(manager)
    
    print(f"\n[OK] 扩充完成！当前模式数量: {len(manager.list_patterns())}")
    print("\n模式分类统计:")
    patterns = manager.list_patterns()
    categories = {}
    for p in patterns:
        cat = p['pattern_id'].split('_')[0]
        categories[cat] = categories.get(cat, 0) + 1
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}个")

if __name__ == "__main__":
    main()
