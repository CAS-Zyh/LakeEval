"""BQI 路由 —— 对接 modules/ 新架构。

批量计算：使用 BenthicBQICalculator.batch_calculate() 处理 CSV/Excel 上传。
单点计算：使用 BenthicBQICalculator.calculate_bqi()。
"""
import io
import csv
import json
from flask import Blueprint, request, jsonify
from sqlalchemy import or_
from ..auth import require_auth
from ..extensions import db
from ..models import CalculationRecord, BenthicSpecies, StandardTolerance
from ..safe_db import safe_commit
from modules.benthic_bqi import (
    BenthicBQICalculator,
    calculate_bqi,
    calculate_bi,
    bqi_grade,
    get_species_list,
    normalize_to_wide,
    BI_GRADE_CRITERIA,
)
from modules.db_manager import (
    get_tolerance_dataframe,
    match_species,
    search_species,
    reload_cache,
    get_tolerance,
)

bqi_bp = Blueprint("bqi", __name__)


def _get_calculator() -> BenthicBQICalculator:
    return BenthicBQICalculator(get_tolerance_dataframe())


def _parse_csv_to_samples(raw_text: str, season: str = "spring"):
    """解析 CSV 文本为样本列表，使用 BenthicBQICalculator 批量计算。"""
    reader = csv.DictReader(io.StringIO(raw_text))
    fieldnames = reader.fieldnames or []
    if "site_name" not in fieldnames or len(fieldnames) < 2:
        return None, "CSV 必须包含 site_name 列和至少一个物种列", []

    calc = _get_calculator()
    rows_list = []
    for row in reader:
        rows_list.append(row)

    if not rows_list:
        return None, "CSV 无有效数据行", []

    import pandas as pd
    df = pd.DataFrame(rows_list)

    result = calc.batch_calculate(df, site_col="site_name", season=season)
    if "error" in result:
        return None, result["error"], []

    return (
        result["samples"],
        None,
        result.get("unknown_species", []),
        result.get("summary", {}),
        result.get("chart_data", {}),
    )


# ── 单点计算 ────────────────────────────────────────────────

@bqi_bp.route("/calculate", methods=["POST"])
@require_auth
def calculate():
    data = request.json or {}
    species_counts = data.get("species_counts", {})
    species_counts = {k: int(v) for k, v in species_counts.items() if int(v) > 0}
    season = data.get("season", "spring")

    calc = _get_calculator()
    result = calc.calculate_bqi(species_counts, season=season)
    result["species_counts"] = species_counts

    if request.current_user.id is not None:
        try:
            record = CalculationRecord(
                user_id=request.current_user.id,
                type="bqi",
                input_data=json.dumps(species_counts),
                result=json.dumps(result),
            )
            db.session.add(record)
            safe_commit()
        except Exception:
            db.session.rollback()
    return jsonify({"success": True, "data": result})


# ── 物种接口 ────────────────────────────────────────────────

@bqi_bp.route("/species", methods=["GET"])
def species():
    return jsonify({
        "success": True,
        "data": get_species_list(),
        "meta": {"scale": "0-100", "source": "standard_tolerance"},
    })


@bqi_bp.route("/species/search", methods=["GET"])
def species_search_r():
    q = (request.args.get("q") or "").strip()
    try:
        page = max(1, int(request.args.get("page", "1")))
    except ValueError:
        page = 1
    try:
        page_size = min(200, max(1, int(request.args.get("page_size", "50"))))
    except ValueError:
        page_size = 50

    records, meta = search_species(query=q, page=page, page_size=page_size)
    return jsonify({"success": True, "data": records, "meta": meta})


@bqi_bp.route("/species/lookup", methods=["GET"])
def species_lookup():
    name = (request.args.get("name") or "").strip()
    if not name:
        return jsonify({"success": False, "error": "缺少 name 参数"}), 400
    tv, matched, level = match_species(name)
    if tv is None:
        return jsonify({
            "success": True,
            "data": {
                "name": name,
                "found": False,
                "tolerance_value": None,
                "match_level": None,
            },
        })
    return jsonify({
        "success": True,
        "data": {
            "name": name,
            "found": True,
            "matched_name": matched,
            "tolerance_value": tv,
            "match_level": level,
        },
    })


@bqi_bp.route("/grades", methods=["GET"])
def grades():
    return jsonify({
        "success": True,
        "data": [
            {"range": f"{lo:.0f}-{hi:.0f}", "name": name, "color": color, "scale": "0-100"}
            for lo, hi, name, color in BI_GRADE_CRITERIA
        ],
    })


# ── 批量计算 ────────────────────────────────────────────────

@bqi_bp.route("/batch_calculate", methods=["POST"])
@require_auth
def batch_calculate():
    """批量上传 CSV/Excel 计算 BQI。

    支持 CSV 和 Excel 格式。POST 参数：
    - file: 上传文件
    - season: "spring" | "autumn"（默认 spring）
    """
    if "file" not in request.files:
        return jsonify({"success": False, "error": "未上传文件"}), 400

    file = request.files["file"]
    season = (request.form.get("season") or "spring").lower()

    try:
        raw_bytes = file.read()
    except Exception as e:
        return jsonify({"success": False, "error": f"文件读取失败: {e}"}), 400

    # 自动检测格式
    filename = (file.filename or "").lower()

    try:
        import pandas as pd
        if filename.endswith(".xlsx") or filename.endswith(".xls"):
            df = pd.read_excel(io.BytesIO(raw_bytes))
        else:
            try:
                raw_text = raw_bytes.decode("utf-8-sig")
            except UnicodeDecodeError:
                raw_text = raw_bytes.decode("gbk", errors="ignore")
            df = pd.read_csv(io.StringIO(raw_text))
    except Exception as e:
        return jsonify({"success": False, "error": f"文件解析失败: {e}"}), 400

    df = normalize_to_wide(df)
    calc = _get_calculator()
    result = calc.batch_calculate(df, site_col="site_name", season=season)

    if "error" in result:
        return jsonify({"success": False, "error": result["error"]}), 400

    return jsonify({
        "success": True,
        "data": {
            "samples": result["samples"],
            "chart_data": result["chart_data"],
            "summary": result["summary"],
            "unknown_species": result["unknown_species"],
            "season": season,
            "season_label": result.get("season_label", ""),
            "scale": "0-100",
        },
    })


@bqi_bp.route("/reload_cache", methods=["POST"])
def reload_cache_r():
    n = reload_cache()
    return jsonify({"success": True, "data": {"cached_entries": n}})