"""
Markdown 输出辅助函数
所有打印到 stdout 的格式化逻辑集中于此。
"""


def h2(title: str) -> None:
    print(f"\n## {title}\n")


def h3(title: str) -> None:
    print(f"\n### {title}\n")


def md_table(headers: list[str], rows: list[list], aligns: list[str] | None = None) -> None:
    """打印 Markdown 表格。aligns: 'l'/'c'/'r' 对应每列对齐方式。"""
    if aligns is None:
        aligns = ['l'] * len(headers)
    sep_map = {'l': ':---', 'c': ':---:', 'r': '---:'}
    seps = [sep_map.get(a, '---') for a in aligns]
    print('| ' + ' | '.join(str(h) for h in headers) + ' |')
    print('| ' + ' | '.join(seps) + ' |')
    for row in rows:
        print('| ' + ' | '.join(str(c) for c in row) + ' |')
    print()


def safe_major_name(name: str) -> str:
    """将专业名转换为安全的文件名（去除特殊字符）。"""
    return name.replace('/', '_').replace('\\', '_').replace('(', '').replace(')', '')
