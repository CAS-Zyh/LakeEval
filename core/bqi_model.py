"""BQI 兼容性重导出层。

核心算法已迁移至 modules/benthic_bqi.py（BenthicBQICalculator 类），
数据库管理已迁移至 modules/db_manager.py。
此文件保留以确保旧引用不中断。
"""
from __future__ import annotations

from modules.benthic_bqi import (
    BenthicBQICalculator,
    calculate_bqi,
    calculate_bi,
    calculate_species_richness_score,
    bqi_grade,
    get_species_list,
    BI_GRADE_CRITERIA,
    BQI_GRADE_CRITERIA,
    DEFAULT_TOLERANCE,
)
from modules.db_manager import (
    load_tolerance_dict as _load_tolerance_dict_from_db,
    get_tolerance as get_tolerance_value,
    reload_cache as reload_tolerance_cache,
    match_species,
    search_species,
    seed_from_json,
    get_tolerance_dataframe,
    FALLBACK_TOLERANCE as BQI_SPECIES_FALLBACK,
)

BQI_SPECIES = BQI_SPECIES_FALLBACK