"""
年级过滤 / 课程白名单（步骤 4）
"""

import pandas as pd

from config import MAJOR_COURSE_WHITELIST


def filter_grade(merged_df: pd.DataFrame, min_grade: int = 21) -> pd.DataFrame:
    """筛选年级 >= min_grade、剔除留学生。"""
    merged_df = merged_df.copy()
    merged_df['年级_int'] = pd.to_numeric(merged_df['年级'], errors='coerce')
    df = merged_df[merged_df['年级_int'] >= min_grade].copy()
    return df[~df['专业'].str.contains('留学生', na=False)].copy()


def apply_course_whitelist(filtered_df: pd.DataFrame) -> pd.DataFrame:
    """对各专业应用计分课程白名单，未配置专业保留所有课程。"""
    parts = []
    for major, group in filtered_df.groupby('专业'):
        major_str = str(major)
        if major_str in MAJOR_COURSE_WHITELIST:
            group = group[group['课程名称'].isin(MAJOR_COURSE_WHITELIST[major_str])].copy()
        parts.append(group)
    return pd.concat(parts, ignore_index=True)
