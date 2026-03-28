"""
钱盘子验证 —— 统计各等级人数 × 金额，与总预算对比。
"""

import pandas as pd

from config import (
    LEVELS, BUDGET_STUDENT_COUNT, BUDGET_PER_STUDENT, AWARD_AMOUNTS,
)
from utils.md import h2, md_table


def validate_budget(
    ranked: pd.DataFrame,
    total_students: int = BUDGET_STUDENT_COUNT,
    budget_per_student: float = BUDGET_PER_STUDENT,
    award_amounts: dict | None = None,
) -> None:
    """统计各等级人数 × 金额，与总预算对比并打印。"""
    if award_amounts is None:
        award_amounts = AWARD_AMOUNTS

    h2("钱盘子验证")
    budget    = total_students * budget_per_student
    level_col = '综合等级' if '综合等级' in ranked.columns else '裸绩等级'

    print(f"| 项目 | 数值 |\n| :--- | ---: |")
    print(f"| 年级总人数 | {total_students} 人 |")
    print(f"| 人均预算 | {budget_per_student:.1f} 元 |")
    print(f"| **总预算** | **{budget:,.1f} 元** |")
    print(f"| 等级列 | {level_col} |\n")
    print("> 特等奖学金不计入预算盘，单独核算。\n")

    rows = []
    total_cost = 0
    special_n, special_amt = 0, award_amounts.get('特等', 0)
    for lv in LEVELS:
        n      = int((ranked[level_col] == lv).sum())
        amount = award_amounts.get(lv, 0)
        if lv == '特等':
            special_n = n
            rows.append([lv, n, f"{amount:,}", f"{n*amount:,}", "⬅ 单独核算"])
            continue
        cost = n * amount
        total_cost += cost
        rows.append([lv, n, f"{amount:,}", f"{cost:,}", ""])
    md_table(['等级', '人数', '单价(元)', '小计(元)', '备注'], rows, ['l', 'r', 'r', 'r', 'l'])

    surplus = budget - total_cost
    flag    = '✅ 盈余' if surplus >= 0 else '❌ 超支'
    print(f"| 项目 | 金额(元) |\n| :--- | ---: |")
    print(f"| 合计（不含特等） | {total_cost:,} |")
    print(f"| 总预算 | {budget:,.1f} |")
    print(f"| **{flag}** | **{surplus:,.1f}** |")
    if special_n:
        print(f"| 特等额外支出（{special_n} 人 × {special_amt}）| {special_n*special_amt:,} |")
    print()
