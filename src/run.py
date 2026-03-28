"""
入口脚本 —— 奖学金评定一键运行
用法：
    cd /home/project/scholarship-evaluation/src
    python run.py
"""

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


def main() -> None:
    root     = Path(__file__).resolve().parent.parent
    data_in  = root / 'data' / 'input'
    data_out = root / 'data' / 'output'

    # ── 日志文件：data/output/logs/run_YYYYMMDD_HHMMSS.md ──────
    ts      = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_dir = data_out / 'logs'
    tee     = _Tee(log_dir / f'run_{ts}.md')
    sys.stdout = tee

    try:
        # 文档标题
        print(f"# 奖学金评定分析报告\n")
        print(f"> 运行时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        _run(data_in, data_out)
    finally:
        sys.stdout = tee._term
        tee.close()
        print(f"\n日志已保存至: {log_dir / f'run_{ts}.md'}")


def _run(data_in: Path, data_out: Path) -> None:
    # ── 文件路径 ────────────────────────────────────────────────
    normal_file = data_in / '22级裸绩点正考.xlsx'
    makeup_file = data_in / '22级裸绩点缓考.xlsx'

    for f in (normal_file, makeup_file):
        if not f.exists():
            print(f"[ERROR] 输入文件不存在: {f}")
            sys.exit(1)

    # ── 流水线 ──────────────────────────────────────────────────
    analyzer = ScholarshipAnalyzer(str(normal_file), str(makeup_file))

    analyzer.clean_data()                           # 第1步
    analyzer.analyze_low_scores()                   # 第2步
    analyzer.merge_exam_data()                      # 第3步
    analyzer.filter_by_grade(min_grade=21)          # 第4步
    analyzer.split_by_major(str(data_out))          # 第5步
    analyzer.calculate_gpa()                        # 第6步
    analyzer.rank_students_by_major()               # 第7步
    analyzer.calculate_comprehensive_rank()         # 第8步
    analyzer.validate_budget()                      # 钱盘子验证
    analyzer.report_adjustment_hints()              # 可调整提示
    analyzer.generate_reports_by_major()
    analyzer.save_results(str(data_out))


if __name__ == '__main__':
    main()
