from flask import Blueprint, request, jsonify
from ..auth import require_auth
from core.reduction import (
    apply_collaborative_reduction,
    solve_uniform_reduction_to_target,
    build_smart_scheme,
    diagnose_nutrient_limitation,
    function_curve,
)
from core.tli_model import evaluate_tli, tli_grade

reduction_bp = Blueprint("reduction", __name__)


def _parse_values(data):
    return {
        "chla": float(data.get("chla", 0)),
        "tp": float(data.get("tp", 0)),
        "tn": float(data.get("tn", 0)),
        "sd": float(data.get("sd", 0)),
        "cod_mn": float(data.get("cod_mn", 0)),
    }


@reduction_bp.route("/diagnose", methods=["POST"])
@require_auth
def diagnose():
    """独立的营养盐限制因子诊断接口：返回当前水体的限制类型和处置建议。"""
    data = request.json or {}
    values = _parse_values(data)
    limitation = diagnose_nutrient_limitation(values)
    return jsonify({"success": True, "data": limitation})


@reduction_bp.route("/collaborative", methods=["POST"])
@require_auth
def collaborative():
    data = request.json or {}
    values = _parse_values(data)
    ratio = float(data.get("reduction_ratio", 0))
    chla_mode = data.get("chla_mode", "auto")
    chla_link_coeff = float(data.get("chla_link_coeff", 0.6))
    target_tli = float(data.get("target_total_tli", 50))

    # 先做限制因子诊断
    limitation = diagnose_nutrient_limitation(values)

    sim_values = apply_collaborative_reduction(
        values, ratio, chla_mode, chla_link_coeff, target_tli,
        limitation=limitation,
    )
    sim_result = evaluate_tli(sim_values)
    current_result = evaluate_tli(values)
    grade_name, grade_color = tli_grade(sim_result["total_tli"])

    return jsonify({"success": True, "data": {
        "current_tli": current_result["total_tli"],
        "simulated_tli": sim_result["total_tli"],
        "simulated_values": sim_values,
        "simulated_single_tli": sim_result["single_tli"],
        "current_single_tli": current_result["single_tli"],
        "grade_name": grade_name,
        "grade_color": grade_color,
        "delta": sim_result["total_tli"] - current_result["total_tli"],
        "limitation": limitation,
    }})


@reduction_bp.route("/uniform", methods=["POST"])
@require_auth
def uniform():
    data = request.json or {}
    values = _parse_values(data)
    target_tli = float(data.get("target_total_tli", 50))
    chla_mode = data.get("chla_mode", "auto")
    chla_link_coeff = float(data.get("chla_link_coeff", 0.6))

    plan = solve_uniform_reduction_to_target(
        values, target_tli, chla_mode, chla_link_coeff
    )
    return jsonify({"success": True, "data": plan})


@reduction_bp.route("/smart", methods=["POST"])
@require_auth
def smart():
    data = request.json or {}
    values = _parse_values(data)
    target_tli = float(data.get("target_total_tli", 50))
    chla_mode = data.get("chla_mode", "auto")
    chla_link_coeff = float(data.get("chla_link_coeff", 0.6))

    scheme = build_smart_scheme(values, target_tli, chla_mode, chla_link_coeff)
    return jsonify({"success": True, "data": scheme})


@reduction_bp.route("/function_curve", methods=["POST"])
@require_auth
def curve():
    data = request.json or {}
    indicator = data.get("indicator", "chla")
    anchor_value = data.get("anchor_value")
    if anchor_value is not None:
        anchor_value = float(anchor_value)
    result = function_curve(indicator, anchor_value)
    return jsonify({"success": True, "data": result})
