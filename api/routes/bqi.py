import json
from flask import Blueprint, request, jsonify
from ..auth import require_auth
from ..extensions import db
from ..models import CalculationRecord
from ..safe_db import safe_commit
from core.bqi_model import calculate_bqi, bqi_grade, get_species_list, BQI_GRADE_CRITERIA

bqi_bp = Blueprint("bqi", __name__)


@bqi_bp.route("/calculate", methods=["POST"])
@require_auth
def calculate():
    data = request.json or {}
    species_counts = data.get("species_counts", {})
    species_counts = {k: int(v) for k, v in species_counts.items() if int(v) > 0}

    bqi_value = calculate_bqi(species_counts)
    grade_name, grade_color = bqi_grade(bqi_value)
    result = {
        "bqi": bqi_value,
        "grade_name": grade_name,
        "grade_color": grade_color,
        "total_count": sum(species_counts.values()),
        "species_counts": species_counts,
    }

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


@bqi_bp.route("/species", methods=["GET"])
def species():
    return jsonify({"success": True, "data": get_species_list()})


@bqi_bp.route("/grades", methods=["GET"])
def grades():
    return jsonify({"success": True, "data": [
        {"range": "0", "name": "严重污染", "color": c[3]}
        for c in BQI_GRADE_CRITERIA
    ]})
