"""
数据清洗 / 无资格识别 / 正缓考合并（步骤 1-3）
"""

import pandas as pd

from config import (
    DISQUALIFIED_VALUES, LOW_SCORE_THRESHOLD,
    MAX_MAKEUP_EXAMS, PLATFORM_KEYWORDS,
)


# ── 第1步 ─────────────────────────────────────────────────────────

def remove_invalid_records(df: pd.DataFrame) -> pd.DataFrame:
    """删除成绩作废的记录（'是否成绩作废' == '是'）。"""
    return df[df['是否成绩作废'] != '是'].copy()


# ── 第2步 ─────────────────────────────────────────────────────────

def find_disqualified(normal_df: pd.DataFrame, makeup_df: pd.DataFrame) -> pd.DataFrame:
    """识别无资格学生记录（低分 / 旷考 / 取消 / 缓考超限），返回带'异常类型'列的 DataFrame。"""

    # 低于阈值
    low = normal_df[
        pd.to_numeric(normal_df['成绩'], errors='coerce') < LOW_SCORE_THRESHOLD
    ].copy()
    low['异常类型'] = f'低分(<{LOW_SCORE_THRESHOLD})'

    # 旷考 / 取消（正考）
    dq_normal = normal_df[normal_df['成绩'].isin(DISQUALIFIED_VALUES)].copy()
    dq_normal['异常类型'] = dq_normal['成绩']

    # 旷考 / 取消（缓考）
    dq_makeup = makeup_df[makeup_df['成绩'].isin(DISQUALIFIED_VALUES)].copy()
    dq_makeup['异常类型'] = dq_makeup['成绩']

    # 缓考超限
    makeup_count = normal_df[normal_df['成绩'] == '缓考'].groupby('学号').size()
    over_ids     = makeup_count[makeup_count > MAX_MAKEUP_EXAMS].index
    over_makeup  = normal_df[
        normal_df['学号'].isin(over_ids) & (normal_df['成绩'] == '缓考')
    ].copy()
    over_makeup['异常类型'] = f'缓考超{MAX_MAKEUP_EXAMS}门'

    return (
        pd.concat([low, dq_normal, dq_makeup, over_makeup], ignore_index=True)
        .drop_duplicates(subset=['学号', '课程名称'], keep='first')
    )


# ── 第3步 ─────────────────────────────────────────────────────────

def merge_exams(normal_df: pd.DataFrame, makeup_df: pd.DataFrame) -> pd.DataFrame:
    """合并正考（去掉缓考行）与缓考数据，剔除网络平台课程。"""
    normal_clean = normal_df[normal_df['成绩'] != '缓考'].copy()
    merged = pd.concat([normal_clean, makeup_df], ignore_index=True)

    platform_mask = merged['课程名称'].str.contains('|'.join(PLATFORM_KEYWORDS), na=False)
    return merged[~platform_mask].copy()
