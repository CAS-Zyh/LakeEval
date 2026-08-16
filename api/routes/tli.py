import json
from flask import Blueprint, request, jsonify
from ..auth import require_auth
from ..extensions import db
from ..models import CalculationRecord
from core.tli_model import evaluate_tli, tli_grade, back_calculate_target

tli_bp = Blueprint("tli", __name__)


@tli_bp.route("/calculate", methods=["POST"])
@require_auth
def calculate():
    data = request.json or {}
    values = {
        "chla": float(data.get("chla", 0)),
        "tp": float(data.get("tp", 0)),
        "tn": float(data.get("tn", 0)),
        "sd": float(data.get("sd", 0)),
        "cod_mn": float(data.get("cod_mn", 0)),
    }
    result = evaluate_tli(values)
    grade_name, grade_color = tli_grade(result["total_tli"])
    result["grade_name"] = grade_name
    result["grade_color"] = grade_color

    if request.current_user.id is not None:
        record = CalculationRecord(
            user_id=request.current_user.id,
            type="tli",
            input_data=json.dumps(values),
            result=json.dumps(result),
        )
        db.session.add(record)
        db.session.commit()
    return jsonify({"success": True, "data": result})


@tli_bp.route("/back_calculate", methods=["POST"])
@require_auth
def back_calculate():
    data = request.json or {}
    values = {
        "chla": float(data.get("chla", 0)),
        "tp": float(data.get("tp", 0)),
        "tn": float(data.get("tn", 0)),
        "sd": float(data.get("sd", 0)),
        "cod_mn": float(data.get("cod_mn", 0)),
    }
    target_tli = float(data.get("target_total_tli", 50))
    main_pollutant = data.get("main_pollutant", "chla")
    result = back_calculate_target(values, target_tli, main_pollutant)
    return jsonify({"success": True, "data": result})


@tli_bp.route("/grades", methods=["GET"])
def grades():
    return jsonify({"success": True, "data": [
        {"range": "<30", "name": "贫营养", "color": "#2ecc71"},
        {"range": "30-50", "name": "中营养", "color": "#f1c40f"},
        {"range": "50-60", "name": "轻度富营养", "color": "#f39c12"},
        {"range": "60-70", "name": "中度富营养", "color": "#e67e22"},
        {"range": ">=70", "name": "重度富营养", "color": "#e74c3c"},
    ]})
