"""
各专业奖学金评定汇总报告（Markdown 控制台输出）
"""

import pandas as pd

from config import LEVELS
from utils.md import h2, h3, md_table


def generate_reports_by_major(ranked: pd.DataFrame, majors: list[str]) -> None:
    """按专业打印奖学金评定汇总报告。"""
    h2("各专业奖学金评定报告")
    all_levels = LEVELS + ['未获得奖学金']

    for major in majors:
        md    = ranked[ranked['专业'] == major]
        total = len(md)
        h3(f"{major}（参评 {total} 人）")

        print(f"绩点范围：{md['总学分绩点'].min():.1f} ~ {md['总学分绩点'].max():.1f}，"
              f"均值：{md['总学分绩点'].mean():.2f}\n")

        dist_rows = [[lv, n, f"{n/total*100:.1f}%"]
                     for lv in all_levels
                     if (n := int((md['裸绩等级'] == lv).sum()))]
        md_table(['等级', '人数', '占比'], dist_rows, ['l', 'r', 'r'])

        print("**前5名**\n")
        top5 = []
        for _, row in md.nsmallest(5, '裸绩排名').iterrows():
            mark = '★' if row['裸绩等级'] == '特等' else ''
            top5.append([int(row['裸绩排名']), f"{mark}{row['姓名']}",
                         f"{row['总学分绩点']:.1f}", row['裸绩等级']])
        md_table(['名次', '姓名', '总学分绩点', '裸绩等级'], top5, ['r', 'l', 'r', 'l'])
