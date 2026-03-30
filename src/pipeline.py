"""
奖学金评定流水线协调层
职责：读取数据 → 按序调用 processing 各步骤 → 维护 self.results → 打印进度。
不包含任何计算逻辑或 Excel 写入逻辑。
"""

import numpy as np
import pandas as pd
from pathlib import Path

from config import LEVELS, SEMESTER_LABEL
from utils.md import h2, h3, md_table, safe_major_name
from utils.excel import save_ranked_results
import processing
import reporting


class ScholarshipAnalyzer:
    def __init__(self, normal_exam_file: str, makeup_exam_file: str,
                 rounding: str = 'floor', auto_adjust: bool = False):
        self.normal_df = pd.read_excel(normal_exam_file)
        self.makeup_df = pd.read_excel(makeup_exam_file)
        self.merged_df = None
        self.results: dict = {}
        self.rounding = rounding      # floor / round / ceil
        self.auto_adjust = auto_adjust

    # ── 第1步 ──────────────────────────────────────────────────────
    def clean_data(self):
        """删除成绩作废记录。"""
        h2("第1步：数据清理")
        before = len(self.normal_df)
        self.normal_df = processing.remove_invalid_records(self.normal_df)
        removed = before - len(self.normal_df)
        md_table(
            ['项目', '数量'],
            [['清理前记录数', before], ['删除成绩作废', removed], ['清理后记录数', len(self.normal_df)]],
            ['l', 'r'],
        )
        self.results['cleaned_normal'] = len(self.normal_df)

    # ── 第2步 ──────────────────────────────────────────────────────
    def analyze_low_scores(self):
        """识别无资格学生（低分 / 旷考 / 取消 / 缓考超限）。"""
        h2("第2步：成绩分析 — 低分 / 旷考 / 取消考试资格")
        disq = processing.find_disqualified(self.normal_df, self.makeup_df)

        print(f"**无资格记录数：{len(disq)} 条，涉及 {disq['学号'].nunique()} 名学生**\n")
        md_table(['异常类型', '记录数'],
                 [[t, n] for t, n in disq['异常类型'].value_counts().items()], ['l', 'r'])

        if len(disq) > 0:
            print("**按专业明细**\n")
            grouped = (disq.groupby(['专业', '学号', '姓名', '异常类型'])
                       .agg({'课程名称': lambda x: '、'.join(x.values)})
                       .reset_index())
            md_table(
                ['专业', '学号', '姓名', '异常类型', '课程'],
                grouped[['专业', '学号', '姓名', '异常类型', '课程名称']].values.tolist(),
                ['l', 'l', 'l', 'l', 'l'],
            )
        self.results['disqualified'] = disq

    # ── 第3步 ──────────────────────────────────────────────────────
    def merge_exam_data(self):
        """合并正考缓考，剔除网络平台课程。"""
        h2("第3步：合并正考与缓考数据")
        before_normal = len(self.normal_df[self.normal_df['成绩'] != '缓考'])
        self.merged_df = processing.merge_exams(self.normal_df, self.makeup_df)
        md_table(
            ['来源', '记录数'],
            [['正考（去缓考标记）', before_normal],
             ['缓考', len(self.makeup_df)],
             ['合并后（去平台课）', len(self.merged_df)]],
            ['l', 'r'],
        )

    # ── 第4步 ──────────────────────────────────────────────────────
    def filter_by_grade(self, min_grade: int = 21):
        """筛选本届及留级学生，剔除留学生。"""
        h2(f"第4步：筛选参评学生（{min_grade}级及以后入学，剔除留学生）")
        if self.merged_df is None:
            raise ValueError("merged_df 为空，请先执行 merge_exam_data()")
        grade_filtered = processing.filter_grade(self.merged_df, min_grade)
        filtered       = processing.apply_course_whitelist(grade_filtered)

        whitelist_rows = []
        for major, group in grade_filtered.groupby('专业'):
            after = len(filtered[filtered['专业'] == major])
            if after != len(group):
                whitelist_rows.append([major, len(group), after, len(group) - after])
        if whitelist_rows:
            print("**课程白名单过滤**\n")
            md_table(['专业', '过滤前', '过滤后', '剔除'], whitelist_rows, ['l', 'r', 'r', 'r'])

        grade_dist = filtered['年级'].value_counts().sort_index()
        print("**年级分布**\n")
        md_table(['年级', '人次'], [[str(g), n] for g, n in grade_dist.items()], ['l', 'r'])
        print(f"> 过滤后总记录：**{len(filtered)} 条**\n")

        self.results['filtered_data'] = filtered
        if '班级' in filtered.columns:
            tmp = filtered.dropna(subset=['班级']).copy()
            tmp['学号'] = tmp['学号'].astype(str).str.replace(r'\.0$', '', regex=True)
            self.results['student_class'] = tmp.groupby('学号')['班级'].first()

    # ── 第5步 ──────────────────────────────────────────────────────
    def split_by_major(self, output_dir: str | None = None):
        """按专业拆分并保存成绩数据。"""
        if output_dir is None:
            output_dir = str(Path(__file__).resolve().parent.parent / 'data/output')
        h2("第5步：按专业拆分并保存成绩数据")

        score_dir = Path(output_dir) / '成绩数据'
        score_dir.mkdir(parents=True, exist_ok=True)
        filtered  = self.results['filtered_data']
        majors    = sorted(filtered['专业'].unique())

        rows = []
        for major in majors:
            df   = filtered[filtered['专业'] == major]
            path = score_dir / f'{SEMESTER_LABEL}_成绩数据_{safe_major_name(major)}.xlsx'
            df.to_excel(path, index=False)
            rows.append([major, len(df), path.name])
        md_table(['专业', '记录数', '文件名'], rows, ['l', 'r', 'l'])
        self.results['majors_raw'] = majors

    # ── 第6步 ──────────────────────────────────────────────────────
    def calculate_gpa(self):
        """按学生汇总，计算裸绩点。"""
        h2("第6步：计算学生绩点")
        gpa = processing.compute_gpa(self.results['filtered_data'])
        print(f"> 参评学生总数：**{len(gpa)}** 人\n")

        desc = gpa[['总学分绩点', '裸绩点']].describe().round(3)
        print("**绩点统计**\n```")
        print(desc.to_string())
        print("```\n")

        print("**各专业前3名**\n")
        for major in sorted(gpa.index.get_level_values('专业').unique()):
            top3 = (pd.DataFrame(gpa.xs(major, level='专业'))
                    .sort_values('总学分绩点', ascending=False).head(3))
            h3(major)
            md_table(
                ['名次', '姓名', '总学分绩点'],
                [[i + 1, idx[1], f"{row['总学分绩点']:.1f}"]
                 for i, (idx, row) in enumerate(top3.iterrows())],
                ['r', 'l', 'r'],
            )
        self.results['student_gpa'] = gpa

    # ── 第7步 ──────────────────────────────────────────────────────
    def rank_students_by_major(self):
        """按专业裸绩排名，分配裸绩等级。"""
        h2("第7步：按专业裸绩排名与奖学金分级")
        eligible_ids = processing.get_special_eligible_ids(self.results['filtered_data'])
        student_gpa  = self.results['student_gpa'].copy().reset_index()
        majors       = sorted(student_gpa['专业'].unique())

        all_ranked = []
        for major in majors:
            ms = (student_gpa[student_gpa['专业'] == major]
                  .sort_values('裸绩点', ascending=False).reset_index(drop=True))
            ms['裸绩排名'] = range(1, len(ms) + 1)
            ms['特等资格']  = ms['学号'].isin(eligible_ids)
            quotas    = processing.compute_quotas(len(ms), self.rounding)
            level_map = processing.assign_naked_levels(ms, eligible_ids, quotas)
            ms['裸绩等级'] = ms['学号'].map(level_map)
            all_ranked.append(ms)

            h3(f"{major}（{len(ms)} 人）")
            rows = [[lv, quotas[lv], int((ms['裸绩等级'] == lv).sum())] for lv in LEVELS]
            rows.append(['未获得奖学金', '—', int((ms['裸绩等级'] == '未获得奖学金').sum())])
            md_table(['等级', '名额', '实际'], rows, ['l', 'r', 'r'])

        ranked   = pd.concat(all_ranked, ignore_index=True).sort_values(['专业', '裸绩排名'])
        disq_ids = set(self.results.get('disqualified', pd.DataFrame()).get('学号', pd.Series()))
        if disq_ids:
            ranked.loc[ranked['学号'].isin(disq_ids), '裸绩等级'] = '无资格'

        self.results['ranked_students'] = ranked
        self.results['majors'] = majors

    # ── 第8步 ──────────────────────────────────────────────────────
    def calculate_comprehensive_rank(self, bonus_file: str | None = None):
        """综合加分 + 综合排名 + 综合等级。"""
        h2("第8步：综合加分与综合等级")
        root = Path(__file__).resolve().parent.parent

        # 同时加载两张加分表，每位学生取最大值
        bonus_map, details = processing.load_merged_bonus_map(root)

        if details:
            for label, cnt in details.items():
                print(f">   · [{label}] 有效加分记录 **{cnt}** 条")
            both = set(details)
            if len(both) == 2:
                print(f">   · 两表共 **{(bonus_map > 0).sum()}** 名学生有加分，取较大值合并\n")
            else:
                print(f">   · 合并后 **{(bonus_map > 0).sum()}** 条有效加分\n")
        else:
            print("> ⚠️ 未找到任何加分表，综合加分全部为 0\n")

        # 兼容外部传入 bonus_file 参数（显式覆盖）
        if bonus_file is not None:
            bonus_map = processing.load_bonus_map_form(bonus_file)
            print(f"> [覆盖] 加分表：`{bonus_file}`，有效记录 **{len(bonus_map)}** 条\n")

        ranked = processing.attach_comprehensive_gpa(self.results['ranked_students'], bonus_map)

        all_comp = []
        for major in self.results['majors']:
            ms       = ranked[ranked['专业'] == major].copy()
            ms_valid = (ms[ms['裸绩等级'] != '无资格']
                        .sort_values('综合绩点', ascending=False).reset_index(drop=True))
            ms_disq  = ms[ms['裸绩等级'] == '无资格'].copy()

            ms_valid['综合排名'] = range(1, len(ms_valid) + 1)
            total_in_major = len(ms)          # 含无资格，用于名额 & 50% 分界线
            quotas   = processing.compute_quotas(total_in_major, self.rounding)
            comp_map = processing.assign_comp_levels(ms_valid, quotas, total_in_major)
            ms_valid['综合等级'] = ms_valid['学号'].map(comp_map)
            ms_disq[['综合排名', '综合等级']] = np.nan, '无资格'
            all_comp.append(pd.concat([ms_valid, ms_disq], ignore_index=True))

        result = pd.concat(all_comp, ignore_index=True)
        self.results['ranked_students'] = result
        print(f"> 综合等级计算完成，共 **{len(result)}** 名学生\n")

    # ── 可调整提示 ─────────────────────────────────────────────────
    def report_adjustment_hints(self):
        """检测同分异级 & 倒挂，仅写入 MD 日志供人工参考，不自动修改等级。"""
        h2("可调整提示（仅供参考，未自动修改）")
        ranked = self.results['ranked_students']
        tied, inversions, surplus = processing.detect_tied_students(ranked)

        print(f"> 当前剩余预算：**{surplus:,.1f} 元**\n")

        # ── 同分异级 ──────────────────────────────────────────
        if tied:
            total_cost = sum(r['需额外支出'] for r in tied)
            print(f"### 同分异级（{len(tied)} 人，全部调整需 {total_cost:,.0f} 元）\n")
            print("> 综合绩点相同，但因名额比例切割落入不同等级：\n")
            md_table(
                ['专业', '学号', '姓名', '裸绩点', '综合加分', '综合绩点',
                 '综合排名', '当前等级', '建议调至', '需额外支出(元)'],
                [
                    [
                        r['专业'], r['学号'], r['姓名'],
                        f"{r['裸绩点']:.3f}", f"{r['综合加分']:.3f}",
                        f"{r['综合绩点']:.3f}", r['综合排名'],
                        r['当前等级'], r['建议调至'],
                        f"{r['需额外支出']:,.0f}",
                    ]
                    for r in tied
                ],
                ['l', 'l', 'l', 'r', 'r', 'r', 'r', 'l', 'l', 'r'],
            )
            print()
        else:
            print("> ✅ 未发现同分异级情况。\n")

        # ── 倒挂 ──────────────────────────────────────────────
        if inversions:
            total_cost = sum(r['需额外支出'] for r in inversions)
            print(f"### 倒挂提示（{len(inversions)} 人，全部修正需 {total_cost:,.0f} 元）\n")
            print("> 综合绩点更高的学生等级反而低于后面的同学：\n")
            md_table(
                ['专业', '学号', '姓名', '裸绩点', '综合加分', '综合绩点',
                 '综合排名', '裸绩等级', '当前等级', '后面最优', '需额外支出(元)'],
                [
                    [
                        r['专业'], r['学号'], r['姓名'],
                        f"{r['裸绩点']:.3f}", f"{r['综合加分']:.3f}",
                        f"{r['综合绩点']:.3f}", r['综合排名'],
                        r['裸绩等级'], r['当前等级'], r['后面最优'],
                        f"{r['需额外支出']:,.0f}",
                    ]
                    for r in inversions
                ],
                ['l', 'l', 'l', 'r', 'r', 'r', 'r', 'l', 'l', 'l', 'r'],
            )
            print()
        else:
            print("> ✅ 未发现倒挂情况。\n")

    def apply_auto_adjustment(self):
        """自动应用同分异级 + 倒挂调整，在预算内贪心分配。
        此方法产生完整的章节输出，不需要额外调用 report_adjustment_hints()。
        """
        h2("同分异级 & 倒挂自动调整")
        ranked = self.results['ranked_students']
        tied, inversions, surplus = processing.detect_tied_students(ranked)

        if not tied and not inversions:
            print(f"> 当前盈余：**{surplus:,.1f} 元**\n")
            print("> ✅ 未发现同分异级或倒挂情况，无需调整。\n")
            return

        adjusted, applied_tied, applied_inv, remaining = \
            processing.apply_adjustments(ranked, tied, inversions, surplus)

        self.results['ranked_students'] = adjusted

        tied_cost = sum(r['需额外支出'] for r in applied_tied)
        inv_cost  = sum(r['需额外支出'] for r in applied_inv)

        # ── 摘要 ──────────────────────────────────────────────
        print(f"> 调整前盈余：**{surplus:,.1f} 元** → 调整后盈余：**{remaining:,.1f} 元**\n")

        skipped_tied = len(tied) - len(applied_tied)
        skipped_inv  = len(inversions) - len(applied_inv)
        if skipped_tied + skipped_inv > 0:
            print(f"> ⚠️ 因预算不足跳过：同分异级 {skipped_tied} 人、倒挂 {skipped_inv} 人\n")

        # ── 同分异级明细 ──────────────────────────────────────
        if applied_tied:
            print(f"### 同分异级调整（已调整 {len(applied_tied)}/{len(tied)} 人，"
                  f"花费 {tied_cost:,.0f} 元）\n")
            md_table(
                ['专业', '学号', '姓名', '裸绩点', '综合绩点',
                 '综合排名', '原等级', '调至', '花费(元)'],
                [
                    [
                        r['专业'], r['学号'], r['姓名'],
                        f"{r['裸绩点']:.3f}", f"{r['综合绩点']:.3f}",
                        r['综合排名'],
                        r['当前等级'], r['建议调至'],
                        f"{r['需额外支出']:,.0f}",
                    ]
                    for r in applied_tied
                ],
                ['l', 'l', 'l', 'r', 'r', 'r', 'l', 'l', 'r'],
            )
            print()
        elif tied:
            print(f"### 同分异级（检测到 {len(tied)} 人，因预算不足均未调整）\n")
        else:
            print("> ✅ 未发现同分异级情况。\n")

        # ── 倒挂明细 ──────────────────────────────────────────
        if applied_inv:
            print(f"### 倒挂修正（已修正 {len(applied_inv)}/{len(inversions)} 人，"
                  f"花费 {inv_cost:,.0f} 元）\n")
            md_table(
                ['专业', '学号', '姓名', '综合绩点',
                 '综合排名', '裸绩等级', '原等级', '调至', '花费(元)'],
                [
                    [
                        r['专业'], r['学号'], r['姓名'],
                        f"{r['综合绩点']:.3f}", r['综合排名'],
                        r['裸绩等级'], r['当前等级'], r['后面最优'],
                        f"{r['需额外支出']:,.0f}",
                    ]
                    for r in applied_inv
                ],
                ['l', 'l', 'l', 'r', 'r', 'l', 'l', 'l', 'r'],
            )
            print()
        elif inversions:
            print(f"### 倒挂提示（检测到 {len(inversions)} 人，因预算不足均未修正）\n")
        else:
            print("> ✅ 未发现倒挂情况。\n")

    # ── 报告 ──────────────────────────────────────────────────────
    def validate_budget(self, **kwargs):
        reporting.validate_budget(self.results['ranked_students'], **kwargs)

    def generate_reports_by_major(self):
        reporting.generate_reports_by_major(
            self.results['ranked_students'], self.results['majors'])

    # ── 保存结果 ──────────────────────────────────────────────────
    def save_results(self, output_dir: str | None = None):
        """委托 utils.excel 保存全部 Excel 文件。"""
        if output_dir is None:
            output_dir = str(Path(__file__).resolve().parent.parent / 'data/output')

        if self.merged_df is None:
            raise ValueError("merged_df 为空，请先执行 merge_exam_data()")

        save_ranked_results(
            ranked_students=self.results['ranked_students'],
            merged_df=self.merged_df,
            class_map=self.results.get('student_class', pd.Series(dtype=str)),
            disqualified=self.results.get('disqualified', pd.DataFrame()),
            output_dir=output_dir,
        )

        # 附件5
        reporting.generate_award_list(
            self.results['ranked_students'],
            self.results.get('student_class', pd.Series(dtype=str)),
            output_dir,
        )

        print("\n✅ **分析完成！**\n")
