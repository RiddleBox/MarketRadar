"""
m7_scheduler/trading_calendar.py — 交易日历判断

判断指定日期是否为交易日（排除周末和节假日）
"""
from datetime import date, datetime
from typing import Optional
import chinese_calendar

from core.schemas import Market


def is_trading_day(market: Market, check_date: Optional[date] = None) -> bool:
    """
    判断指定日期是否为交易日
    
    Args:
        market: 市场
        check_date: 检查日期，默认今天
    
    Returns:
        True=交易日，False=休市
    """
    if check_date is None:
        check_date = date.today()
    
    if market == Market.A_SHARE:
        # A股：使用 chinese_calendar 库判断（包含法定节假日）
        return chinese_calendar.is_workday(check_date)
    
    elif market == Market.HK:
        # 港股：简化处理，只判断周末（TODO: 集成港股节假日）
        weekday = check_date.weekday()
        return weekday < 5
    
    elif market == Market.US:
        # 美股：简化处理，只判断周末（TODO: 集成美股节假日）
        weekday = check_date.weekday()
        return weekday < 5
    
    return True


def is_market_open(market: Market, check_time: Optional[datetime] = None) -> bool:
    """
    判断指定时间市场是否开盘
    
    Args:
        market: 市场
        check_time: 检查时间，默认当前时间
    
    Returns:
        True=开盘中，False=闭市
    """
    if check_time is None:
        check_time = datetime.now()
    
    # 先判断是否交易日
    if not is_trading_day(market, check_time.date()):
        return False
    
    hour = check_time.hour
    minute = check_time.minute
    time_int = hour * 100 + minute
    
    if market == Market.A_SHARE:
        # A股：09:30-11:30, 13:00-15:00
        return (930 <= time_int <= 1130) or (1300 <= time_int <= 1500)
    
    elif market == Market.HK:
        # 港股：09:30-12:00, 13:00-16:00
        return (930 <= time_int <= 1200) or (1300 <= time_int <= 1600)
    
    elif market == Market.US:
        # 美股：21:30-04:00（北京时间，夏令时）
        # 简化处理：只判断时间段，不考虑夏令时切换
        return (2130 <= time_int <= 2359) or (0 <= time_int <= 400)
    
    return False
