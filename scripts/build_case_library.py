#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
案例库构建脚本
从2023-2024年重要历史案例中提取经验教训
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Windows控制台UTF-8编码
if sys.platform == 'win32':
    os.system('chcp 65001 > nul')
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from m2_storage.case_library import CaseLibraryManager
from core.schemas import Market


def build_initial_cases():
    """构建初始案例库"""
    manager = CaseLibraryManager()
    
    cases = [
        # 1. 新能源政策案例
        {
            "case_id": "case_2023_ev_subsidy",
            "date_range_start": datetime(2023, 6, 15),
            "date_range_end": datetime(2023, 7, 30),
            "market": Market.A_SHARE,
            "signal_sequence": ["新能源汽车购置税减免政策延续至2025年", "市场情绪修复", "龙头企业受益"],
            "evolution": "政策公布后，新能源板块止跌企稳，龙头企业率先反弹，带动产业链上下游跟涨",
            "outcome": {"event_occurred": True, "market_reaction": 0.185, "time_to_event": 45},
            "lessons": "政策延续消除了市场最大担忧；龙头企业受益最明显；需要等待市场情绪修复后再入场",
            "tags": ["新能源", "政策利好", "龙头股"],
        },
        
        # 2. 业绩预增案例
        {
            "case_id": "case_2023_earnings_beat",
            "date_range_start": datetime(2023, 10, 20),
            "date_range_end": datetime(2023, 11, 19),
            "market": Market.A_SHARE,
            "signal_sequence": ["某半导体公司Q3业绩预增150%-180%", "产业链联动", "快速兑现"],
            "evolution": "业绩预告发布后，该公司连续涨停，产业链上游公司跟涨，30天内完成主升浪",
            "outcome": {"event_occurred": True, "market_reaction": 0.253, "time_to_event": 30},
            "lessons": "业绩超预期是最强催化剂；产业链联动效应明显；需要快速兑现，避免追高",
            "tags": ["业绩预增", "半导体", "超预期"],
        },
        
        # 3. 地缘政治风险案例
        {
            "case_id": "case_2024_geopolitical",
            "date_range_start": datetime(2024, 2, 10),
            "date_range_end": datetime(2024, 2, 25),
            "market": Market.A_SHARE,
            "signal_sequence": ["中东地缘冲突升级", "原油价格暴涨", "避险情绪升温"],
            "evolution": "地缘风险爆发后，全球股市恐慌性下跌，黄金和国债成为避险首选，15天内完成避险交易",
            "outcome": {"event_occurred": True, "market_reaction": 0.087, "time_to_event": 15},
            "lessons": "地缘风险是短期避险机会；黄金和国债是最佳避险资产；需要快速止盈，风险溢价会迅速消退",
            "tags": ["地缘政治", "避险", "黄金"],
        },
        
        # 4. 央行降息案例
        {
            "case_id": "case_2024_rate_cut",
            "date_range_start": datetime(2024, 3, 5),
            "date_range_end": datetime(2024, 3, 25),
            "market": Market.A_SHARE,
            "signal_sequence": ["央行意外降息25bp", "宽松信号释放", "估值修复"],
            "evolution": "降息后银行股估值修复，地产股反弹乏力，20天内完成交易",
            "outcome": {"event_occurred": True, "market_reaction": 0.052, "time_to_event": 20},
            "lessons": "降息利好已被部分定价；银行股受益于估值修复；地产股需要基本面配合，单纯政策不够",
            "tags": ["货币政策", "降息", "银行股"],
        },
        
        # 5. 技术突破案例
        {
            "case_id": "case_2024_tech_breakthrough",
            "date_range_start": datetime(2024, 4, 12),
            "date_range_end": datetime(2024, 5, 7),
            "market": Market.A_SHARE,
            "signal_sequence": ["国产AI芯片性能突破", "概念炒作", "缺乏订单验证"],
            "evolution": "技术突破消息发布后短期冲高，但缺乏商业化订单支撑，25天内回落",
            "outcome": {"event_occurred": False, "market_reaction": -0.123, "time_to_event": 25},
            "lessons": "技术突破需要商业化验证；市场对概念炒作已疲劳；需要等待实际订单落地",
            "tags": ["技术突破", "AI芯片", "概念炒作"],
        },
        
        # 6. 外资流入案例
        {
            "case_id": "case_2023_northbound",
            "date_range_start": datetime(2023, 11, 8),
            "date_range_end": datetime(2024, 1, 7),
            "market": Market.A_SHARE,
            "signal_sequence": ["北向资金连续5日净流入超100亿", "外资加速配置", "白马龙头受益"],
            "evolution": "外资持续流入，白酒、医药龙头估值修复，60天内完成中期趋势",
            "outcome": {"event_occurred": True, "market_reaction": 0.158, "time_to_event": 60},
            "lessons": "外资持续流入是中期趋势信号；白马龙头是外资首选；需要耐心持有，不要被短期波动吓出",
            "tags": ["北向资金", "外资", "白马股"],
        },
        
        # 7. 行业整顿案例
        {
            "case_id": "case_2023_regulation",
            "date_range_start": datetime(2023, 7, 20),
            "date_range_end": datetime(2023, 7, 20),
            "market": Market.A_SHARE,
            "signal_sequence": ["教育行业监管政策收紧", "多家公司被约谈", "市场恐慌"],
            "evolution": "监管政策出台后，教育板块持续下跌，未参与抄底，规避风险",
            "outcome": {"event_occurred": True, "market_reaction": 0.0, "time_to_event": 0},
            "lessons": "监管政策是最大风险；不要试图抄底政策风险股；等待政策明朗后再考虑",
            "tags": ["监管政策", "教育", "风险规避"],
        },
        
        # 8. 并购重组案例
        {
            "case_id": "case_2024_ma",
            "date_range_start": datetime(2024, 1, 15),
            "date_range_end": datetime(2024, 2, 24),
            "market": Market.A_SHARE,
            "signal_sequence": ["重大资产重组公告", "注入优质资产", "小盘股催化剂"],
            "evolution": "重组公告后，股价连续涨停，40天内完成主升浪",
            "outcome": {"event_occurred": True, "market_reaction": 0.325, "time_to_event": 40},
            "lessons": "重组是小盘股的重要催化剂；需要评估注入资产的质量；重组预期兑现后要及时止盈",
            "tags": ["并购重组", "资产注入", "小盘股"],
        },
        
        # 9. 业绩爆雷案例
        {
            "case_id": "case_2023_earnings_miss",
            "date_range_start": datetime(2023, 8, 25),
            "date_range_end": datetime(2023, 9, 4),
            "market": Market.A_SHARE,
            "signal_sequence": ["白马股业绩大幅低于预期", "商誉减值", "未及时止损"],
            "evolution": "业绩爆雷后连续跌停，10天内损失惨重",
            "outcome": {"event_occurred": True, "market_reaction": -0.287, "time_to_event": 10},
            "lessons": "业绩爆雷要第一时间止损；白马股也会有黑天鹅；不要对任何股票有信仰",
            "tags": ["业绩爆雷", "止损", "风险管理"],
        },
        
        # 10. 技术面突破案例
        {
            "case_id": "case_2024_breakout",
            "date_range_start": datetime(2024, 3, 20),
            "date_range_end": datetime(2024, 4, 24),
            "market": Market.A_SHARE,
            "signal_sequence": ["突破长期盘整区间", "成交量放大", "基本面改善"],
            "evolution": "技术突破后，股价沿趋势上涨，35天内完成主升浪",
            "outcome": {"event_occurred": True, "market_reaction": 0.221, "time_to_event": 35},
            "lessons": "技术突破需要成交量配合；基本面改善是突破的基础；突破后要设置止损，防止假突破",
            "tags": ["技术突破", "放量", "趋势跟踪"],
        },
    ]
    
    print("开始构建案例库...")
    print(f"准备导入 {len(cases)} 个案例")
    
    success_count = 0
    for case_data in cases:
        if manager.add_case(**case_data):
            success_count += 1
            print(f"[OK] 导入案例: {case_data['case_id']}")
        else:
            print(f"❌ 导入失败: {case_data['case_id']}")
    
    print(f"\n[OK] 案例库构建完成！成功导入 {success_count}/{len(cases)} 个案例")
    
    # 测试查询功能
    print("\n测试案例查询功能:")
    print("=" * 50)
    
    # 查询新能源相关案例
    print("\n1. 查询新能源相关案例:")
    ev_cases = manager.search_cases(["新能源", "政策"])
    for case in ev_cases[:3]:
        print(f"  - {case.case_id}: {case.signal_sequence[0][:30]}... ({case.outcome})")
    
    # 查询业绩/突破相关案例
    print("\n2. 查询业绩/突破相关案例:")
    profitable_cases = manager.search_cases(["业绩", "突破"])
    for case in profitable_cases[:3]:
        pnl = case.outcome.get('market_reaction', 0) * 100
        print(f"  - {case.case_id}: {case.signal_sequence[0][:30]}... (收益率: {pnl:.1f}%)")
    
    # 查询风险案例
    print("\n3. 查询风险案例:")
    risk_cases = manager.search_cases(["监管", "爆雷"])
    for case in risk_cases[:3]:
        print(f"  - {case.case_id}: {case.signal_sequence[0][:30]}... ({case.lessons[:20]}...)")
    
    print("\n[OK] 最终统计:")
    all_cases = manager.list_cases()
    print(f"  总案例数: {len(all_cases)}")
    print(f"  最早案例: {all_cases[-1]['date_range'] if all_cases else 'N/A'}")
    print(f"  最新案例: {all_cases[0]['date_range'] if all_cases else 'N/A'}")


if __name__ == "__main__":
    build_initial_cases()
