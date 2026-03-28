"""
入口脚本 —— 奖学金评定一键运行
用法：
    cd /home/project/scholarship-evaluation/src
    python run.py                          # 默认截断法，仅提示
    python run.py --rounding round         # 四舍五入
    python run.py --rounding ceil          # 进一法
    python run.py --auto-adjust            # 自动调整，保存到 adjusted/ 子文件夹
    python run.py --rounding ceil --auto-adjust
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

# 允许在任意目录执行：把 src/ 加到 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline import ScholarshipAnalyzer


class _Tee:
    """将 stdout 同时写到终端和日志文件。"""
    def __init__(self, log_path: Path):
        self._term = sys.stdout
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(log_path, 'w', encoding='utf-8')

    def write(self, msg):
        self._term.write(msg)
        self._file.write(msg)

    def flush(self):
        self._term.flush()
        self._file.flush()

    def close(self):
        self._file.close()


_ROUNDING_LABELS = {'floor': '截断法', 'round': '四舍五入', 'ceil': '进一法'}


def main() -> None:
    parser = argparse.ArgumentParser(description='奖学金评定一键运行')
    parser.add_argument(
        '--rounding', choices=['floor', 'round', 'ceil'], default='floor',
        help='名额取整方式: floor=截断(默认), round=四舍五入, ceil=进一',
    )
    parser.add_argument(
        '--auto-adjust', action='store_true', default=False,
        help='启用自动调整（同分异级+倒挂），结果保存到 adjusted/ 子文件夹',
    )
    args = parser.parse_args()

    root     = Path(__file__).resolve().parent.parent
    data_in  = root / 'data' / 'input'
    data_out = root / 'data' / 'output'

    # ── 根据模式选择输出根目录 ──────────────────────────────────
    if args.auto_adjust:
        out_root = root / 'data' / 'output_adjusted'
    else:
        out_root = data_out

    # ── 日志文件：<out_root>/logs/run_YYYYMMDD_HHMMSS.md ───────
    ts      = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_dir = out_root / 'logs'
    tee     = _Tee(log_dir / f'run_{ts}.md')
    sys.stdout = tee

    try:
        # 文档标题
        print(f"# 奖学金评定分析报告\n")
        print(f"> 运行时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        print(f"> 名额取整方式：**{_ROUNDING_LABELS[args.rounding]}**（`--rounding {args.rounding}`）\n")
        if args.auto_adjust:
            print("> ✅ 已启用自动调整（`--auto-adjust`）\n")
        _run(data_in, out_root, rounding=args.rounding,
             auto_adjust=args.auto_adjust)
    finally:
        sys.stdout = tee._term
        tee.close()
        print(f"\n日志已保存至: {log_dir / f'run_{ts}.md'}")


def _run(data_in: Path, data_out: Path, rounding: str = 'floor',
         auto_adjust: bool = False) -> None:
    # ── 文件路径 ────────────────────────────────────────────────
    normal_file = data_in / '22级裸绩点正考.xlsx'
    makeup_file = data_in / '22级裸绩点缓考.xlsx'

    for f in (normal_file, makeup_file):
        if not f.exists():
            print(f"[ERROR] 输入文件不存在: {f}")
            sys.exit(1)

    # ── 流水线 ──────────────────────────────────────────────────
    analyzer = ScholarshipAnalyzer(str(normal_file), str(makeup_file),
                                   rounding=rounding,
                                   auto_adjust=auto_adjust)

    analyzer.clean_data()                           # 第1步
    analyzer.analyze_low_scores()                   # 第2步
    analyzer.merge_exam_data()                      # 第3步
    analyzer.filter_by_grade(min_grade=21)          # 第4步
    analyzer.split_by_major(str(data_out))          # 第5步
    analyzer.calculate_gpa()                        # 第6步
    analyzer.rank_students_by_major()               # 第7步
    analyzer.calculate_comprehensive_rank()         # 第8步
    analyzer.validate_budget()                      # 钱盘子验证

    if auto_adjust:
        analyzer.apply_auto_adjustment()            # 自动调整（含检测+应用+输出）
        analyzer.validate_budget()                  # 重新验证钱盘子
    else:
        analyzer.report_adjustment_hints()          # 可调整提示（仅供参考）

    analyzer.generate_reports_by_major()
    analyzer.save_results(str(data_out))


if __name__ == '__main__':
    main()
