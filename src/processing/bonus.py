"""
综合加分表加载（步骤 8 —— IO 部分）
两张加分表自动识别 + 合并取最大值。
"""

import glob
import pandas as pd
from pathlib import Path


def load_bonus_map_form(bonus_file: str) -> pd.Series:
    """读取《综合奖学金加分表单》（学生提交表单）。
    列名：综合加分绩点（总计），首行为子标题需 skiprows=[1]。
    """
    bonus_col = '综合加分绩点（总计）'
    df = pd.read_excel(bonus_file, skiprows=[1])
    df['学号'] = df['学号'].astype(str).str.replace(r'\.0$', '', regex=True)
    return (
        df.dropna(subset=['学号', bonus_col])
        .set_index('学号')[bonus_col]
        .pipe(pd.to_numeric, errors='coerce')
        .fillna(0)
    )


def load_bonus_map_simple(bonus_file: str) -> pd.Series:
    """读取《综合加分绩点》简表（列名：学号/加分），无需 skiprows。"""
    df = pd.read_excel(bonus_file)
    df['学号'] = df['学号'].astype(str).str.replace(r'\.0$', '', regex=True)
    return (
        df.dropna(subset=['学号', '加分'])
        .set_index('学号')['加分']
        .pipe(pd.to_numeric, errors='coerce')
        .fillna(0)
    )


def find_bonus_files(root: Path) -> dict:
    """在 data/input/ 下搜索两张加分表，返回 {'表单': 路径, '简表': 路径}。"""
    form_candidates = glob.glob(str(root / 'data/input/*表单*.xlsx'))
    simple_candidates = [
        f for f in (
            glob.glob(str(root / 'data/input/*加分绩点*.xlsx'))
            + glob.glob(str(root / 'data/input/*加分*.xlsx'))
        )
        if '表单' not in f
    ]
    return {
        '表单': form_candidates[0]   if form_candidates   else None,
        '简表': simple_candidates[0] if simple_candidates else None,
    }


def load_merged_bonus_map(root: Path) -> tuple[pd.Series, dict]:
    """加载两张加分表并取每个学号的最大值。
    返回 (merged_series, details) 其中 details 包含各来源记录数供日志打印。
    """
    files = find_bonus_files(root)
    maps: list[pd.Series] = []
    details: dict[str, int] = {}

    if files['表单']:
        s = load_bonus_map_form(files['表单'])
        maps.append(s)
        details['表单'] = int((s > 0).sum())

    if files['简表']:
        s = load_bonus_map_simple(files['简表'])
        maps.append(s)
        details['简表'] = int((s > 0).sum())

    if not maps:
        return pd.Series(dtype=float), details

    merged = pd.concat(maps, axis=1).max(axis=1)
    return merged, details


# ── 向后兼容 ─────────────────────────────────────────────────────

def load_bonus_map(bonus_file: str) -> pd.Series:
    """[向后兼容] 读取表单形式加分表。"""
    return load_bonus_map_form(bonus_file)


def find_bonus_file(root: Path) -> str | None:
    """[向后兼容] 仅返回表单文件路径。"""
    return find_bonus_files(root).get('表单')
