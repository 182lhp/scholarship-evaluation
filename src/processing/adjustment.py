"""
同分调级 —— 找出裸绩点 + 综合加分完全相同但因名额切割落入不同等级的学生，
用剩余预算将较低等级的学生上调至同组最高等级。
"""

import pandas as pd

from config import (
    LEVELS, LEVEL_ORDER, AWARD_AMOUNTS,
    BUDGET_STUDENT_COUNT, BUDGET_PER_STUDENT,
)


def _current_spend(df: pd.DataFrame, award_amounts: dict) -> float:
    """统计当前总支出（不含特等，因为特等单独核算）。"""
    cost = 0
    for lv, amt in award_amounts.items():
        if lv == '特等':
            continue
        cost += int((df['综合等级'] == lv).sum()) * amt
    return cost


def adjust_tied_students(
    ranked: pd.DataFrame,
    total_students: int = BUDGET_STUDENT_COUNT,
    budget_per_student: float = BUDGET_PER_STUDENT,
    award_amounts: dict | None = None,
) -> tuple[pd.DataFrame, list[dict]]:
    """
    在综合等级分配完成后，按专业查找"同裸绩点 + 同综合加分"却处于不同等级的学生组，
    将较低等级的学生上调至同组最高等级（不含特等），直到剩余预算耗尽。

    参数
    ----
    ranked : DataFrame  含 综合等级 列的排名表
    total_students : int  年级总人数（用于计算总预算）
    budget_per_student : float  人均预算
    award_amounts : dict  各等级金额

    返回
    ----
    (adjusted_df, adjustments)
        adjusted_df : 调整后的 DataFrame
        adjustments : 每次调整的详细记录列表
    """
    if award_amounts is None:
        award_amounts = AWARD_AMOUNTS

    df = ranked.copy()
    total_budget = total_students * budget_per_student
    remaining = total_budget - _current_spend(df, award_amounts)
    adjustments: list[dict] = []

    # 不参与调级的等级
    skip_levels = {'无资格', '特等'}

    for major in sorted(df['专业'].unique()):
        mask = (df['专业'] == major) & (~df['综合等级'].isin(skip_levels))
        major_df = df.loc[mask]

        # 按（裸绩点, 综合加分）分组
        groups = major_df.groupby(['裸绩点', '综合加分'])

        for (naked_gpa, bonus), grp in groups:
            if len(grp) < 2:
                continue

            levels_in_group = grp['综合等级'].unique()
            if len(levels_in_group) < 2:
                continue  # 同组同等级，无需调整

            # 目标等级：组内最高（LEVEL_ORDER 值最小），排除 '特等'
            target_level = min(
                levels_in_group,
                key=lambda lv: LEVEL_ORDER.get(lv, 99),
            )
            target_amount = award_amounts.get(target_level, 0)

            # 收集需要提升的学生，按所需费用从低到高排序（优先提升代价小的）
            candidates = []
            for idx, row in grp.iterrows():
                cur_lv = row['综合等级']
                if cur_lv == target_level:
                    continue
                cur_amount = award_amounts.get(cur_lv, 0)
                cost_diff = target_amount - cur_amount
                if cost_diff <= 0:
                    continue
                candidates.append((idx, row, cur_lv, cost_diff))

            candidates.sort(key=lambda c: c[3])

            for idx, row, cur_lv, cost_diff in candidates:
                if remaining >= cost_diff:
                    remaining -= cost_diff
                    df.at[idx, '综合等级'] = target_level
                    adjustments.append({
                        '专业': major,
                        '学号': row['学号'],
                        '姓名': row['姓名'],
                        '裸绩点': naked_gpa,
                        '综合加分': bonus,
                        '综合绩点': row['综合绩点'],
                        '综合排名': row.get('综合排名', ''),
                        '原等级': cur_lv,
                        '调整为': target_level,
                        '额外支出': cost_diff,
                        '剩余预算': remaining,
                    })

    return df, adjustments
