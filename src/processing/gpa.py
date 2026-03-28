"""
绩点计算（步骤 6）
"""

import numpy as np
import pandas as pd

from config import SPECIAL_SCORE_MIN


def compute_gpa(filtered_df: pd.DataFrame) -> pd.DataFrame:
    """按学生汇总学分绩点，返回含 '总学分绩点'/'总学分'/'裸绩点' 的 DataFrame（MultiIndex）。"""
    df = filtered_df.copy()
    df['学分绩点_num'] = pd.to_numeric(df['学分绩点'], errors='coerce')
    df['学分_num']    = pd.to_numeric(df['学分'],    errors='coerce')

    gpa = df.groupby(['学号', '姓名', '专业', '学院']).agg(
        总学分绩点=('学分绩点_num', 'sum'),
        总学分=    ('学分_num',    'sum'),
    )
    gpa['裸绩点'] = (gpa['总学分绩点'] / gpa['总学分'].replace(0, np.nan)).round(3)
    return gpa


def get_special_eligible_ids(filtered_df: pd.DataFrame) -> set:
    """返回全科最低分 > SPECIAL_SCORE_MIN 的学号集合（特等资格候选）。"""
    df = filtered_df.copy()
    df['成绩_num'] = pd.to_numeric(df['成绩'], errors='coerce')
    return set(
        df.groupby('学号')['成绩_num'].min()
        .pipe(lambda s: s[s > SPECIAL_SCORE_MIN]).index
    )
