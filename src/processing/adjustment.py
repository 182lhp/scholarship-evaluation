"""
同分异级 & 倒挂检测（仅提示，不自动调整）
扫描所有专业，找出：
  1. 裸绩点 + 综合加分完全相同但因名额切割落入不同等级的学生组
  2. 综合绩点更高的学生等级反而更低的"倒挂"
将结果以建议列表返回，供人工决策。
"""

import pandas as pd

from config import (
    LEVELS, LEVEL_ORDER, GRADE_IDX, AWARD_AMOUNTS,
    BUDGET_STUDENT_COUNT, BUDGET_PER_STUDENT,
)

# GRADE_IDX 反查表
_IDX_TO_LV = {v: k for k, v in GRADE_IDX.items()}


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
    # 规则：综合等级最多只能比裸绩等级提升一档（且不可达特等），
    #       已经提升过的学生无法再从钱盘子调整。
    #       裸绩同分最佳排名在后50%的，天花板为单项。
    inversions: list[dict] = []

    for major in sorted(df['专业'].unique()):
        mask_all  = df['专业'] == major
        half      = mask_all.sum() / 2          # 专业总人数（含无资格）的50%

        mask = mask_all & (~df['综合等级'].isin(skip_levels))
        idxs = df.loc[mask].sort_values('综合排名').index.tolist()
        if not idxs:
            continue

        # 同裸绩点 → 最佳裸绩排名
        major_df = df.loc[mask]
        best_rank_map = major_df.groupby('裸绩点')['裸绩排名'].transform('min')

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

            if cur_order <= best_below_order:
                continue

            # ── 升档上限检查 ──────────────────────────────
            naked_lv = df.at[i, '裸绩等级']
            naked_idx = GRADE_IDX.get(naked_lv, 5)
            cur_idx   = GRADE_IDX.get(cur_lv, 5)

            if naked_lv == '特等':
                continue

            # 单项(4)/未获得奖学金(5) 升一档 → 三等；其余升一档但不可达特等
            cap_upgrade = 3 if naked_idx >= 4 else max(naked_idx - 1, 1)

            # 同裸绩点最佳排名在后50% → 天花板为单项(4)
            best_rank = best_rank_map.at[i]
            cap_bottom50 = 4 if best_rank > half else 0
            max_allowed_idx = max(cap_upgrade, cap_bottom50)

            # 已经升满一档 → 无法再从钱盘子调
            if cur_idx <= max_allowed_idx:
                continue

            # 建议目标不能超过升档上限
            target_idx = GRADE_IDX.get(best_below_lv, 5)
            if target_idx < max_allowed_idx:
                best_below_lv = _IDX_TO_LV[max_allowed_idx]

            # 调整后可能和当前等级相同 → 无需提示
            if GRADE_IDX.get(best_below_lv, 5) >= cur_idx:
                continue

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
                '裸绩等级': naked_lv,
                '当前等级': cur_lv,
                '后面最优': best_below_lv,
                '需额外支出': cost_diff,
            })

    return tied, inversions, surplus


def apply_adjustments(
    ranked: pd.DataFrame,
    tied: list[dict],
    inversions: list[dict],
    surplus: float,
    award_amounts: dict | None = None,
) -> tuple[pd.DataFrame, list[dict], list[dict], float]:
    """
    在预算允许的范围内，按费用从低到高贪心地应用同分异级 + 倒挂调整。

    返回
    ----
    (adjusted_df, applied_tied, applied_inv, remaining_surplus)
    """
    if award_amounts is None:
        award_amounts = AWARD_AMOUNTS

    df = ranked.copy()
    remaining = surplus

    # 合并两种建议，按费用升序贪心调整
    all_suggestions = []
    for r in tied:
        all_suggestions.append(('tied', r, r['需额外支出'], r['建议调至']))
    for r in inversions:
        all_suggestions.append(('inv', r, r['需额外支出'], r['后面最优']))
    all_suggestions.sort(key=lambda x: x[2])

    applied_tied: list[dict] = []
    applied_inv:  list[dict] = []

    for kind, rec, cost, target_lv in all_suggestions:
        if cost > remaining:
            continue
        sid = rec['学号']
        mask = df['学号'] == sid
        if mask.sum() == 0:
            continue
        df.loc[mask, '综合等级'] = target_lv
        remaining -= cost
        if kind == 'tied':
            applied_tied.append(rec)
        else:
            applied_inv.append(rec)

    return df, applied_tied, applied_inv, remaining
