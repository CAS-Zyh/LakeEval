"""Benthic Quality Index (BQI) computation."""

from __future__ import annotations

from typing import Dict, Tuple

BQI_SPECIES: Dict[str, float] = {
    "颤蚓属": 0, "水丝蚓属": 0, "带丝蚓属": 0, "盲蚓属": 0,
    "仙女虫属": 1, "尾盘虫属": 1, "管水蚓属": 1, "摇蚊幼虫": 1, "红虫": 1,
    "多足摇蚊": 2, "小摇蚊": 2, "长足摇蚊": 2, "双翅目幼虫": 2,
    "石蛾幼虫": 3, "蜉蝣幼虫": 3, "蜻蜒幼虫": 3, "豆娘幼虫": 3,
    "毛翅目幼虫": 3, "软体动物": 3, "螺类": 3, "蜻蜓若虫": 3, "蜉蝣若虫": 3,
    "蚌类": 4, "河蚬": 4, "襀翅目若虫": 4, "石蝇幼虫": 4,
    "钩虾": 4, "端足类": 4, "十足类": 4,
    "清洁种": 5,
}

BQI_GRADE_CRITERIA = [
    (0, 0, "严重污染", "#ff0044"),
    (1, 2, "重度污染", "#ff4400"),
    (2, 3, "中度污染", "#ffaa00"),
    (3, 4, "轻度污染", "#aaff00"),
    (4, 6, "清洁", "#00ff88"),
]


def calculate_bqi(species_counts: Dict[str, int]) -> float:
    total_individuals = sum(species_counts.values())
    if total_individuals == 0:
        return 0.0

    weighted_sum = 0.0
    for species, count in species_counts.items():
        si = BQI_SPECIES.get(species, 2)
        weighted_sum += si * count

    return weighted_sum / total_individuals


def bqi_grade(bqi_value: float) -> Tuple[str, str]:
    for lower, upper, name, color in BQI_GRADE_CRITERIA:
        if lower <= bqi_value < upper:
            return name, color
    return "严重污染", "#ff0044"


def get_species_list() -> list:
    groups = [
        ["颤蚓属", "水丝蚓属", "带丝蚓属", "盲蚓属"],
        ["仙女虫属", "尾盘虫属", "管水蚓属", "摇蚊幼虫"],
        ["红虫", "多足摇蚊", "小摇蚊", "长足摇蚊"],
        ["石蛾幼虫", "蜉蝣幼虫", "蜻蜒幼虫", "豆娘幼虫"],
        ["毛翅目幼虫", "双翅目幼虫", "线虫", "软体动物"],
        ["螺类", "蚌类", "河蚬", "蜻蜓若虫"],
        ["蜉蝣若虫", "襀翅目若虫", "石蝇幼虫", "钩虾"],
        ["端足类", "十足类", "清洁种"],
    ]
    result = []
    for group in groups:
        for species in group:
            if species:
                result.append({"name": species, "si": BQI_SPECIES.get(species, 2)})
    return result
