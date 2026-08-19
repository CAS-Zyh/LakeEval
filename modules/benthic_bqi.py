"""底栖动物 BQI（Benthic Quality Index）核心算法。

BQI 由两部分组成：
  1. BI 生物指数（Biotic Index）    → 加权耐污值均值 Σ(Si × ni) / N
  2. 种类数得分（Species Richness） → 基于物种丰富度的修正

核心类 BenthicBQICalculator：
- 由 db_manager.get_tolerance_dataframe() 初始化
- 支持春/秋季节切换（影响 BI 计算参数）
- 智能物种名对齐（属名精确 → 科名精确 → 模糊匹配）
- 多点位批量计算

依赖：modules/db_manager.py 提供耐污值 DataFrame 与物种匹配。
"""
from __future__ import annotations

import math
import re
from typing import Dict, List, Optional, Tuple

import pandas as pd

# ═══════════════════════════════════════════════════════════════
# 分级标准（0-100，BQI = 50×(10-BI)/(10-BI_ref) + 50×S/S_ref）
# ═══════════════════════════════════════════════════════════════
BI_GRADE_CRITERIA = [
    (85.0, 100.01, "非常健康", "#00ff88"),
    (70.0, 85.0, "健康", "#aaff00"),
    (55.0, 70.0, "亚健康", "#ffaa00"),
    (40.0, 55.0, "不健康", "#ff4400"),
    (0.0, 40.0, "非常不健康", "#ff0044"),
]

# 兼容旧名
BQI_GRADE_CRITERIA = BI_GRADE_CRITERIA

# 季节参数：BI_ref（BI 期望值）、S_ref（物种数期望值）
# 按流域结合海拔分区确定
SEASON_DEFAULTS = {
    "spring": {"bi_ref": 6.09, "s_ref": 20, "label": "春季"},
    "autumn": {"bi_ref": 5.44, "s_ref": 17, "label": "秋季"},
}

# 旧版兜底字典（仅当 database 不可用时）
FALLBACK_TOLERANCE: Dict[str, float] = {
    "颤蚓属": 0, "水丝蚓属": 0, "带丝蚓属": 0, "盲蚓属": 0,
    "仙女虫属": 1, "尾盘虫属": 1, "管水蚓属": 1, "摇蚊幼虫": 1, "红虫": 1,
    "多足摇蚊": 2, "小摇蚊": 2, "长足摇蚊": 2, "双翅目幼虫": 2,
    "石蛾幼虫": 3, "蜉蝣幼虫": 3, "蜻蜒幼虫": 3, "豆娘幼虫": 3,
    "毛翅目幼虫": 3, "软体动物": 3, "螺类": 3, "蜻蜓若虫": 3, "蜉蝣若虫": 3,
    "蚌类": 4, "河蚬": 4, "襀翅目若虫": 4, "石蝇幼虫": 4,
    "钩虾": 4, "端足类": 4, "十足类": 4,
    "清洁种": 5,
}

DEFAULT_TOLERANCE = 5.0

# 常见物种别名映射（第 1 级匹配：同义词/常见种名 → 标准检索名）
ALIAS_MAP: Dict[str, str] = {
    "霍甫水丝蚓": "水丝蚓属",
    "纹沼螺": "沼螺属",
    "石田螺": "石田螺属",
    "铜锈环棱螺": "环棱螺属",
    "苏氏尾秀体虫": "尾秀体虫属",
}


def normalize_to_wide(df: pd.DataFrame) -> pd.DataFrame:
    """将长格式数据透视为宽格式（供 batch_calculate 使用）。

    长格式（每行一条记录，样点可重复）：
        样点,鉴定单元,物种数量
        湖心_01,杆丝蚓属,12

    转成宽格式（第一列 site_name，其余列为物种名，值为个体数）。
    若已是宽格式则原样返回。
    """
    site_col = next((c for c in df.columns if str(c).strip() in ("样点", "站点", "site", "site_name")), None)
    species_col = next((c for c in df.columns if str(c).strip() in ("鉴定单元", "物种", "物种名", "taxon", "species")), None)
    count_col = next((c for c in df.columns if str(c).strip() in ("物种数量", "数量", "个体数", "count", "abundance")), None)

    if not (site_col and species_col and count_col):
        return df

    df = df.copy()
    df[count_col] = pd.to_numeric(df[count_col], errors="coerce").fillna(0)

    wide = df.pivot_table(
        index=site_col,
        columns=species_col,
        values=count_col,
        aggfunc="sum",
        fill_value=0,
    ).reset_index()

    return wide.rename(columns={site_col: "site_name"})


# ═══════════════════════════════════════════════════════════════
# BenthicBQICalculator
# ═══════════════════════════════════════════════════════════════

class BenthicBQICalculator:
    """底栖动物 BQI 计算器。

    初始化：
        from modules.db_manager import get_tolerance_dataframe
        calc = BenthicBQICalculator(get_tolerance_dataframe())

    用法：
        result = calc.calculate_bqi({"颤蚓属": 120, "蜉蝣幼虫": 50}, season="spring")
        print(result["bqi"], result["grade_name"])
    """

    def __init__(self, tolerance_df: pd.DataFrame):
        """用耐污值 DataFrame 初始化。

        tolerance_df 列：phylum, class_name, order_name, family, genus, tolerance_value
        """
        self.tolerance_df = tolerance_df
        self._genus_index: Dict[str, float] = {}
        self._family_index: Dict[str, float] = {}
        self._order_index: Dict[str, float] = {}
        self._class_index: Dict[str, float] = {}
        self._phylum_index: Dict[str, float] = {}
        self._name_records: Dict[str, dict] = {}
        self._build_index()

    def _build_index(self):
        """构建属→科→目→纲→门 各分类层级的名称→耐污值索引，并缓存完整分类记录。"""
        self._genus_index.clear()
        self._family_index.clear()
        self._order_index.clear()
        self._class_index.clear()
        self._phylum_index.clear()
        self._name_records.clear()

        if self.tolerance_df.empty:
            return

        df = self.tolerance_df
        for _, row in df.iterrows():
            record = {
                "phylum": str(row.get("phylum", "") or "").strip(),
                "class_name": str(row.get("class_name", "") or "").strip(),
                "order_name": str(row.get("order_name", "") or "").strip(),
                "family": str(row.get("family", "") or "").strip(),
                "genus": str(row.get("genus", "") or "").strip(),
                "tolerance_value": float(row["tolerance_value"]),
            }
            for col, index in (
                ("genus", self._genus_index),
                ("family", self._family_index),
                ("order_name", self._order_index),
                ("class_name", self._class_index),
                ("phylum", self._phylum_index),
            ):
                key = record[col]
                if not key:
                    continue
                if key not in index:
                    index[key] = record["tolerance_value"]
                if key not in self._name_records:
                    self._name_records[key] = record

    # ── 物种名对齐 ──────────────────────────────────────────

    def align_species(self, species_names: List[str]) -> Dict[str, dict]:
        """批量对齐物种名到耐污值。

        匹配顺序：属 → 科 → 目 → 纲 → 门，逐级向上；再模糊、兜底、默认。
        返回 {原始名: {tolerance_value, matched_name, match_level}}
        match_level: genus|family|order|class|phylum|fuzzy|fallback|unmatched
        """
        results = {}
        for name in species_names:
            n = (name or "").strip()
            if not n:
                continue
            resolved = self._resolve_full(n)
            results[name] = {
                "tolerance_value": resolved["tolerance_value"],
                "matched_name": resolved["matched_name"],
                "match_level": resolved["match_level"],
            }
        return results

    def _exact_lookup(self, name: str) -> Optional[Tuple[float, str]]:
        """第 2 级：属 → 科 → 目 → 纲 → 门 逐级精确匹配。

        返回 (tolerance_value, match_level) 或 None。
        """
        for level, index in (
            ("genus", self._genus_index),
            ("family", self._family_index),
            ("order", self._order_index),
            ("class", self._class_index),
            ("phylum", self._phylum_index),
        ):
            if name in index:
                return float(index[name]), level
        return None

    def _substring_lookup(self, name: str) -> Optional[Tuple[float, str, str]]:
        """第 3 级：双向子串与后缀剥离匹配。

        将数据库名称去掉"属/科/目/纲/门"等后缀得到核心串，再判断核心串与输入名
        是否互相包含。例如输入"霍甫水丝蚓"命中"水丝蚓属"、输入"纹沼螺"命中"沼螺属"。
        返回 (tolerance_value, match_level, matched_name) 或 None。
        """
        suffix_re = re.compile(r"(属|科|亚科|总科|目|纲|门|亚门)$")
        for level, index in (
            ("genus", self._genus_index),
            ("family", self._family_index),
            ("order", self._order_index),
            ("class", self._class_index),
            ("phylum", self._phylum_index),
        ):
            for key, tv in index.items():
                core = suffix_re.sub("", key).strip()
                if core and (core in name or name in core):
                    return float(tv), level, key
        return None

    # ── BI 生物指数 ─────────────────────────────────────────

    def calculate_bi(self, species_counts: Dict[str, int]) -> float:
        """BI = Σ(Si × ni) / N

        Si：物种耐污值（0-10，值越高越耐污）
        ni：物种个体数
        N：总个体数
        """
        total_individuals = sum(species_counts.values())
        if total_individuals == 0:
            return 0.0

        weighted_sum = 0.0
        for name, count in species_counts.items():
            si = self._resolve_tolerance(name)
            weighted_sum += si * count

        return weighted_sum / total_individuals

    def _resolve_full(self, name: str) -> Dict[str, object]:
        """多级匹配流水线：同义词映射 → 精确全匹配 → 双向子串降级 → 兜底/未匹配。

        返回 {tolerance_value, match_level, matched_name, match_method}。
        match_method: 精确匹配 / 同义词映射 (原始名 -> 标准名) / 子串降级匹配 (原始名 -> 命中名) / 兜底降级 / 未匹配
        """
        n = (name or "").strip()
        if not n:
            return {
                "tolerance_value": DEFAULT_TOLERANCE,
                "match_level": "unmatched",
                "matched_name": None,
                "match_method": "未匹配",
            }

        # 第 1 级：同义词/常见种名映射表
        if n in ALIAS_MAP:
            target = ALIAS_MAP[n]
            exact = self._exact_lookup(target)
            if exact:
                return {
                    "tolerance_value": exact[0],
                    "match_level": exact[1],
                    "matched_name": target,
                    "match_method": f"同义词映射 ({n} -> {target})",
                }

        # 第 2 级：精确全匹配
        exact = self._exact_lookup(n)
        if exact:
            return {
                "tolerance_value": exact[0],
                "match_level": exact[1],
                "matched_name": n,
                "match_method": "精确匹配",
            }

        # 第 3 级：双向子串与后缀剥离匹配
        sub = self._substring_lookup(n)
        if sub:
            return {
                "tolerance_value": sub[0],
                "match_level": sub[1],
                "matched_name": sub[2],
                "match_method": f"子串降级匹配 ({n} -> {sub[2]})",
            }

        # 第 4 级：兜底降级
        if n in FALLBACK_TOLERANCE:
            return {
                "tolerance_value": FALLBACK_TOLERANCE[n],
                "match_level": "fallback",
                "matched_name": n,
                "match_method": "兜底降级",
            }

        return {
            "tolerance_value": DEFAULT_TOLERANCE,
            "match_level": "unmatched",
            "matched_name": None,
            "match_method": "未匹配",
        }

    def _resolve_tolerance(self, name: str) -> float:
        """解析单个物种名的耐污值（多级匹配流水线）。"""
        return float(self._resolve_full(name)["tolerance_value"])

    # ── 种类数得分 ──────────────────────────────────────────

    def calculate_species_richness_score(self, species_count: int, season: str = "spring") -> float:
        """S/S_ref 比值（上限 1.0）。

        S：底栖动物物种数监测值（分类单元数）
        S_ref：期望值（春季 20 种，秋季 17 种）
        """
        params = SEASON_DEFAULTS.get(season, SEASON_DEFAULTS["spring"])
        s_ref = params["s_ref"]
        if s_ref <= 0:
            return 0.0
        ratio = species_count / s_ref
        return min(ratio, 1.0)

    # ── 综合 BQI ────────────────────────────────────────────

    def calculate_bqi(
        self,
        species_counts: Dict[str, int],
        season: str = "spring",
    ) -> dict:
        """综合 BQI = 50 × (10-BI)/(10-BI_ref) + 50 × S/S_ref。

        式中：
        - BI：底栖动物 BI 指数监测值
        - BI_ref：期望值（春季 6.09，秋季 5.44）
        - S：物种数监测值
        - S_ref：期望值（春季 20，秋季 17）
        - 两比值上限均为 1.0

        返回：
            {bqi, bi, bi_ratio, s_ratio, s_ref, grade_name, grade_color, ...}
        """
        season = season.lower() if season else "spring"
        if season not in SEASON_DEFAULTS:
            season = "spring"

        params = SEASON_DEFAULTS[season]
        bi_ref = params["bi_ref"]
        s_ref = params["s_ref"]

        bi = self.calculate_bi(species_counts)
        total_count = sum(species_counts.values())
        species_count = len(species_counts)

        # (10-BI)/(10-BI_ref)，上限 1.0
        if bi_ref >= 10:
            bi_ratio = 1.0
        else:
            bi_ratio = min((10.0 - bi) / (10.0 - bi_ref), 1.0)

        # S/S_ref，上限 1.0
        s_ratio = self.calculate_species_richness_score(species_count, season)

        # BI 得分值 = 50 × (10-BI)/(10-BI_ref)
        bi_score = 50.0 * bi_ratio
        # 物种数得分值 = 50 × S/S_ref
        s_score = 50.0 * s_ratio

        # BQI 得分（100 分制）= BI得分值 + 物种数得分值
        bqi = bi_score + s_score
        # 兼容旧字段：BQI 指数（0-1）
        bqi_index = 0.5 * bi_ratio + 0.5 * s_ratio
        grade_name, grade_color = self.grade(bqi)

        return {
            "bqi": round(bqi, 3),
            "bqi_index": round(bqi_index, 4),
            "bi": round(bi, 3),
            "bi_ratio": round(bi_ratio, 4),
            "s_ratio": round(s_ratio, 4),
            "bi_score": round(bi_score, 3),
            "s_score": round(s_score, 3),
            "bi_ref": bi_ref,
            "s_ref": s_ref,
            "total_count": total_count,
            "species_count": species_count,
            "grade_name": grade_name,
            "grade_color": grade_color,
            "season": season,
            "season_label": params["label"],
            "scale": "0-100",
        }

    # ── 分级 ────────────────────────────────────────────────

    @staticmethod
    def grade(bqi_value: float) -> Tuple[str, str]:
        """根据 BQI 值返回 (等级名称, 颜色)。BQI 越高越清洁。"""
        for lower, upper, name, color in BI_GRADE_CRITERIA:
            if lower <= bqi_value < upper:
                return name, color
        return "非常不健康", "#ff0044"

    # ── 多点位批量计算 ──────────────────────────────────────

    def batch_calculate(
        self,
        df: pd.DataFrame,
        site_col: str = "site_name",
        season: str = "spring",
    ) -> dict:
        """多点位批量计算 BQI。

        参数：
            df: 宽格式 DataFrame，行为站点，列为物种名（第一列 site_col）
            site_col: 站点列名
            season: "spring" | "autumn"

        返回：
            {
                "samples": [{site_name, bqi, bi, grade_name, grade_color, ...}],
                "summary": {count, avg_bqi, best_site, worst_site, ...},
                "unknown_species": [...],
                "chart_data": {sites, bqi_values, grade_colors, grade_names},
                "season": str,
                "scale": "0-100",
            }
        """
        if site_col not in df.columns:
            return {"error": f"DataFrame 缺少 {site_col} 列"}

        species_cols = [c for c in df.columns if c != site_col]
        samples = []
        unknown_species = []
        seen_unknown = set()

        for _, row in df.iterrows():
            site = str(row[site_col]).strip()
            if not site:
                continue

            counts = {}
            matched_details = []
            for col in species_cols:
                try:
                    n = int(float(row[col] or 0))
                except (ValueError, TypeError):
                    continue
                if n <= 0:
                    continue

                resolved = self._resolve_full(col)
                tv = resolved["tolerance_value"]
                match_level = resolved["match_level"]
                match_method = resolved.get("match_method", match_level)
                if match_level == "unmatched":
                    if col not in seen_unknown:
                        seen_unknown.add(col)
                        unknown_species.append(col)

                counts[col] = n
                matched_details.append({
                    "name": col,
                    "count": n,
                    "tolerance_value": tv,
                    "match_level": match_level,
                    "match_method": match_method,
                    "matched_name": resolved.get("matched_name"),
                })

            if not counts:
                continue

            result = self.calculate_bqi(counts, season)
            samples.append({
                "site_name": site,
                "bqi": result["bqi"],
                "bqi_index": result["bqi_index"],
                "bi": result["bi"],
                "bi_ratio": result["bi_ratio"],
                "s_ratio": result["s_ratio"],
                "bi_score": result["bi_score"],
                "s_score": result["s_score"],
                "grade_name": result["grade_name"],
                "grade_color": result["grade_color"],
                "total_count": result["total_count"],
                "species_count": result["species_count"],
                "species_counts": counts,
                "matched_details": matched_details,
            })

        if not samples:
            return {"error": "未解析出有效数据"}

        bqi_values = [s["bqi"] for s in samples]
        bi_values = [s["bi"] for s in samples]
        summary = {
            "count": len(samples),
            "avg_bqi": round(sum(bqi_values) / len(bqi_values), 3),
            "avg_bi": round(sum(bi_values) / len(bi_values), 3),
            "max_bqi": round(max(bqi_values), 3),
            "min_bqi": round(min(bqi_values), 3),
            "best_site": samples[bqi_values.index(max(bqi_values))]["site_name"],
            "worst_site": samples[bqi_values.index(min(bqi_values))]["site_name"],
        }

        return {
            "samples": samples,
            "summary": summary,
            "unknown_species": unknown_species,
            "chart_data": {
                "sites": [s["site_name"] for s in samples],
                "bqi_values": [s["bqi"] for s in samples],
                "bi_values": [s["bi"] for s in samples],
                "bi_scores": [s["bi_score"] for s in samples],
                "s_scores": [s["s_score"] for s in samples],
                "grade_colors": [s["grade_color"] for s in samples],
                "grade_names": [s["grade_name"] for s in samples],
            },
            "season": season,
            "season_label": SEASON_DEFAULTS[season]["label"],
            "scale": "0-100",
        }


# ═══════════════════════════════════════════════════════════════
# 兼容旧版函数接口（保留给 api/routes/ 等旧调用方）
# ═══════════════════════════════════════════════════════════════

def calculate_bi(species_counts: Dict[str, int]) -> float:
    """兼容旧接口：直接调用计算器。"""
    from .db_manager import get_tolerance_dataframe
    calc = BenthicBQICalculator(get_tolerance_dataframe())
    return calc.calculate_bi(species_counts)


def calculate_bqi(species_counts: Dict[str, int]) -> float:
    """兼容旧接口：返回 float（BQI 值）。"""
    calc = _get_cached_calculator()
    return calc.calculate_bqi(species_counts)["bqi"]


def calculate_species_richness_score(species_count: int, season: str = "spring") -> float:
    """兼容旧接口。"""
    calc = _get_cached_calculator()
    return calc.calculate_species_richness_score(species_count, season)


def bqi_grade(bqi_value: float) -> Tuple[str, str]:
    return BenthicBQICalculator.grade(bqi_value)


def get_species_list() -> List[dict]:
    """兼容旧接口：返回简化物种列表。"""
    from .db_manager import get_tolerance_dataframe, FALLBACK_TOLERANCE, DEFAULT_TOLERANCE
    result = []
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
    df = get_tolerance_dataframe()
    calc = BenthicBQICalculator(df)
    for group in groups:
        for species in group:
            if species:
                si = calc._resolve_tolerance(species)
                result.append({"name": species, "si": si})
    return result


# 模块级缓存计算器
_calc_instance: Optional[BenthicBQICalculator] = None


def _get_cached_calculator() -> BenthicBQICalculator:
    global _calc_instance
    if _calc_instance is None:
        from .db_manager import get_tolerance_dataframe
        _calc_instance = BenthicBQICalculator(get_tolerance_dataframe())
    return _calc_instance