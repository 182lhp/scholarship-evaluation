"""
名额计算 / 裸绩等级分配 / 综合等级分配（步骤 7-8）
"""

import math
import pandas as pd

from config import LEVELS, RATIOS, GRADE_IDX


# 取整策略映射
_ROUNDING_FUNCS = {
    'floor': int,                        # 截断（向下取整）
    'round': lambda x: int(round(x)),    # 四舍五入
    'ceil':  math.ceil,                  # 进一法
}


def compute_quotas(total: int, rounding: str = 'floor') -> dict:
    """
    计算各等级名额，至少为 1。
    rounding: 'floor'（截断）| 'round'（四舍五入）| 'ceil'（进一法）
    """
    fn = _ROUNDING_FUNCS.get(rounding, int)
    return {lv: max(1, fn(total * r)) for lv, r in zip(LEVELS, RATIOS)}


def assign_naked_levels(major_df: pd.DataFrame, eligible_ids: set, quotas: dict) -> dict:
    """
    对单个专业的学生（已按裸绩点降序排列）分配裸绩等级。
    返回 {学号: 等级} 映射字典。
    """
    top_eligible = major_df.head(quotas['特等']).loc[
        major_df.head(quotas['特等'])['特等资格'], '学号'
    ].tolist()

    remaining = major_df[~major_df['学号'].isin(top_eligible)].copy()
    level_map = {sid: '特等' for sid in top_eligible}
    pos = 0
    for lv in LEVELS[1:]:
        for _, row in remaining.iloc[pos:pos + quotas[lv]].iterrows():
            level_map[row['学号']] = lv
        pos += quotas[lv]
    for _, row in major_df.iterrows():
        if row['学号'] not in level_map:
            level_map[row['学号']] = '未获得奖学金'
    return level_map


# ── 综合等级 ─────────────────────────────────────────────────────

def attach_comprehensive_gpa(ranked: pd.DataFrame, bonus_map: pd.Series) -> pd.DataFrame:
    """在 ranked 上附加 '综合加分' 和 '综合绩点' 列，返回新 DataFrame。"""
    df = ranked.copy()
    sid = df['学号'].astype(str).str.replace(r'\.0$', '', regex=True)
    df['综合加分'] = sid.map(bonus_map).fillna(0).round(3)
    df['综合绩点'] = (df['裸绩点'].fillna(0) + df['综合加分']).round(3)
    return df


def _max_allowed_idx(effective_lv: str, naked_rank: int, half: float) -> int:
    """
    计算单个学生的最高允许综合等级索引（越小越高档）。
    规则：
    - 特等保留特等（返回 0）
    - 以 effective_lv（同裸绩点中最高等级）为基础，最多升一档，
      且不能达到特等（索引最小为 1）
    - 单项/未获得奖学金升一档 → 三等（单项为独立类别）
    - 裸绩排名后 50% 上限为单项（索引 4）
    """
    if effective_lv == '特等':
        return 0
    eff_idx = GRADE_IDX.get(effective_lv, 5)
    # 单项(4)/未获得奖学金(5) 升一档进入三等，而非单项
    cap_upgrade = 3 if eff_idx >= 4 else max(eff_idx - 1, 1)
    cap_bottom50 = 4 if naked_rank > half else 0
    return max(cap_upgrade, cap_bottom50)


def assign_comp_levels(ms_valid: pd.DataFrame, quotas: dict,
                       total_in_major: int | None = None) -> dict:
    """
    对单专业有效学生（已按综合绩点降序排列）分配综合等级。
    返回 {学号: 综合等级} 映射字典。

    升档基础修正：若学生裸绩点与更高等级的同学相同（同分因名额被
    降等），则以同裸绩点中最高裸绩等级为升档基础。

    total_in_major: 专业总人数（含无资格），用于计算 50% 分界线。
                    未提供时退回到 len(ms_valid)。
    """
    half = (total_in_major or len(ms_valid)) / 2

    # 同裸绩点 → 最高裸绩等级（GRADE_IDX 越小档次越高）
    naked_idx_series = ms_valid['裸绩等级'].map(lambda lv: GRADE_IDX.get(lv, 5))
    best_by_gpa = naked_idx_series.groupby(ms_valid['裸绩点']).transform('min')
    # 反查等级名称
    idx_to_lv = {v: k for k, v in GRADE_IDX.items()}
    effective_lv_series = best_by_gpa.map(idx_to_lv)

    # 同裸绩点 → 最佳裸绩排名（同分不因排名靠后被卡50%）
    best_rank_series = ms_valid['裸绩排名'].groupby(ms_valid['裸绩点']).transform('min')

    max_idx = [
        _max_allowed_idx(eff_lv, best_rank, half)
        for eff_lv, best_rank
        in zip(effective_lv_series, best_rank_series)
    ]

    special_ids = set(ms_valid[ms_valid['裸绩等级'] == '特等']['学号'])
    comp_map    = {sid: '特等' for sid in special_ids}
    assigned    = set(special_ids)

    rows = list(ms_valid.itertuples(index=False))

    for lv_idx, lv in enumerate(LEVELS[1:], start=1):
        filled = 0
        for i, row in enumerate(rows):
            if filled >= quotas[lv]:
                break
            sid = row.学号
            if sid in assigned:
                continue
            if max_idx[i] <= lv_idx:
                comp_map[sid] = lv
                assigned.add(sid)
                filled += 1

    for row in rows:
        if row.学号 not in comp_map:
            comp_map[row.学号] = '未获得奖学金'

    return comp_map
