"""
同分异级 & 倒挂检测（仅提示，不自动调整）
扫描所有专业，找出：
  1. 裸绩点 + 综合加分完全相同但因名额切割落入不同等级的学生组
  2. 综合绩点更高的学生等级反而更低的"倒挂"
将结果以建议列表返回，供人工决策。
"""

import pandas as pd

from config import (
    LEVELS, LEVEL_ORDER, AWARD_AMOUNTS,
    BUDGET_STUDENT_COUNT, BUDGET_PER_STUDENT,
)


def _current_spend(df: pd.DataFrame, award_amounts: dict) -> float:
    """统计当前总支出（不含特等）。"""
    cost = 0
    for lv, amt in award_amounts.items():
        if lv == '特等':
            continue
        cost += int((df['综合等级'] == lv).sum()) * amt
    return cost


def detect_tied_students(
    ranked: pd.DataFrame,
    total_students: int = BUDGET_STUDENT_COUNT,
    budget_per_student: float = BUDGET_PER_STUDENT,
    award_amounts: dict | None = None,
) -> tuple[list[dict], list[dict], float]:
    """
    检测同分异级和倒挂情况，**不修改数据**，仅返回建议。

    返回
    ----
    (tied_suggestions, inversion_suggestions, surplus)
        tied_suggestions      : 同分异级建议列表
        inversion_suggestions : 倒挂建议列表
        surplus               : 当前剩余预算
    """
    if award_amounts is None:
        award_amounts = AWARD_AMOUNTS

    df = ranked
    total_budget = total_students * budget_per_student
    surplus = total_budget - _current_spend(df, award_amounts)

    skip_levels = {'无资格', '特等'}
    tied: list[dict] = []

    # ── 同分异级检测 ──────────────────────────────────────────
    for major in sorted(df['专业'].unique()):
        mask = (df['专业'] == major) & (~df['综合等级'].isin(skip_levels))
        major_df = df.loc[mask]

        groups = major_df.groupby(['裸绩点', '综合加分'])
        for (naked_gpa, bonus), grp in groups:
            if len(grp) < 2:
                continue
            levels_in_group = grp['综合等级'].unique()
            if len(levels_in_group) < 2:
                continue

            target_level = min(
                levels_in_group,
                key=lambda lv: LEVEL_ORDER.get(lv, 99),
            )
            target_amount = award_amounts.get(target_level, 0)

            for _, row in grp.iterrows():
                cur_lv = row['综合等级']
                if cur_lv == target_level:
                    continue
                cur_amount = award_amounts.get(cur_lv, 0)
                cost_diff = target_amount - cur_amount
                if cost_diff <= 0:
                    continue
                tied.append({
                    '专业': major,
                    '学号': row['学号'],
                    '姓名': row['姓名'],
                    '裸绩点': naked_gpa,
                    '综合加分': bonus,
                    '综合绩点': row['综合绩点'],
                    '综合排名': row.get('综合排名', ''),
                    '当前等级': cur_lv,
                    '建议调至': target_level,
                    '需额外支出': cost_diff,
                })

    # ── 倒挂检测 ──────────────────────────────────────────────
    inversions: list[dict] = []

    for major in sorted(df['专业'].unique()):
        mask = (df['专业'] == major) & (~df['综合等级'].isin(skip_levels))
        idxs = df.loc[mask].sort_values('综合排名').index.tolist()
        if not idxs:
            continue

        cur_best_order = LEVEL_ORDER.get('未获得奖学金', 99)
        cur_best_level = '未获得奖学金'
        suffix_best = {}
        for i in reversed(idxs):
            lv = df.at[i, '综合等级']
            lv_order = LEVEL_ORDER.get(lv, 99)
            if lv_order < cur_best_order:
                cur_best_order = lv_order
                cur_best_level = lv
            suffix_best[i] = (cur_best_level, cur_best_order)

        for i in idxs:
            cur_lv = df.at[i, '综合等级']
            cur_order = LEVEL_ORDER.get(cur_lv, 99)
            best_below_lv, best_below_order = suffix_best[i]

            if cur_order > best_below_order:
                row = df.loc[i]
                cur_amount = award_amounts.get(cur_lv, 0)
                target_amount = award_amounts.get(best_below_lv, 0)
                cost_diff = max(target_amount - cur_amount, 0)
                inversions.append({
                    '专业': major,
                    '学号': row['学号'],
                    '姓名': row['姓名'],
                    '裸绩点': row['裸绩点'],
                    '综合加分': row['综合加分'],
                    '综合绩点': row['综合绩点'],
                    '综合排名': row.get('综合排名', ''),
                    '当前等级': cur_lv,
                    '后面最优': best_below_lv,
                    '需额外支出': cost_diff,
                })

    return tied, inversions, surplus
