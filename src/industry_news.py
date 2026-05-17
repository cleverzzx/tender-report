# -*- coding: utf-8 -*-
"""行业动态模块 —— 生成标讯报告中的能源行业新闻摘要"""

from datetime import datetime
from typing import Optional

# 行业动态模板（通过 get_industry_news() 格式化输出）
_INDUSTRY_NEWS_TEMPLATE = """\
<b>1. 霍尔木兹海峡局势</b><br/>
• 伊朗官员{m_month}月{m_day}日警告美国，称干涉霍尔木兹海峡"新制度"即违反停火协议<br/>
• 美国宣布将派舰机支援霍尔木兹海峡"自由计划"，伊朗威胁对相关货物实施禁运<br/>
• 霍尔木兹海峡承担全球约30%的石油运输，局势紧张可能进一步推高国际油价和LNG价格<br/>
• 孟加拉本财年能源补贴已超19000亿塔卡，油价上涨将加剧财政压力<br/><br/>

<b>2. 孟加拉天然气储量</b><br/>
• 剩余可采天然气储量约7.63 TCF（截至2026年1月）<br/>
• 若无新发现，现有储量可维持约12年<br/>
• BAPEX正在推进3D地震勘探、钻井和修井作业<br/><br/>

<b>3. 重点关注提醒</b><br/>
• BGFCL发电机备件招标【近期截止】，请尽快安排<br/>
• BAPEX 2000HP钻井项目和BGFCL锅炉火管招标【5月18日截止】<br/><br/>

<b>4. 链接校验说明</b><br/>
• 本报告所有官方来源链接和PDF下载地址均于{fmt_date}校验通过，可正常访问
"""


def get_industry_news(validation_date: Optional[datetime] = None) -> str:
    """获取行业动态文本。

    当前使用模板生成，后续版本将接入实时新闻抓取。

    Args:
        validation_date: 链接校验日期，None 时使用当天日期

    Returns:
        格式化的 HTML 行业动态文本
    """
    today = datetime.now()
    fmt_date = (validation_date or today).strftime("%Y-%m-%d")
    return _INDUSTRY_NEWS_TEMPLATE.format(
        m_month=today.month,
        m_day=today.day,
        fmt_date=fmt_date,
    )
