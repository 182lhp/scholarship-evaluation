"""processing 包 —— re-export 所有纯数据处理函数，供 pipeline 直接导入。"""

from processing.cleaning import remove_invalid_records, find_disqualified, merge_exams
from processing.filtering import filter_grade, apply_course_whitelist
from processing.gpa import compute_gpa, get_special_eligible_ids
from processing.ranking import (
    compute_quotas, assign_naked_levels,
    assign_comp_levels, attach_comprehensive_gpa,
)
from processing.bonus import (
    load_bonus_map_form, load_bonus_map_simple,
    find_bonus_files, load_merged_bonus_map,
    load_bonus_map, find_bonus_file,
)
from processing.adjustment import detect_tied_students, apply_adjustments
