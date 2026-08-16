import json
import io
import csv
from flask import Blueprint, request, jsonify, Response
from ..auth import require_auth
from ..models import CalculationRecord
from ..extensions import db

records_bp = Blueprint("records", __name__)


@records_bp.route("", methods=["GET"])
@require_auth
def list_records():
    # 游客无持久化记录，返回空列表
    if request.current_user.role == "guest":
        return jsonify({"success": True, "data": []})

    record_type = request.args.get("type")
    limit = min(int(request.args.get("limit", 50)), 200)

    query = CalculationRecord.query
    if request.current_user.role != "admin":
        query = query.filter_by(user_id=request.current_user.id)
    if record_type:
        query = query.filter_by(type=record_type)
    records = query.order_by(CalculationRecord.created_at.desc()).limit(limit).all()
    return jsonify({"success": True, "data": [r.to_dict() for r in records]})


@records_bp.route("/<int:record_id>", methods=["GET"])
@require_auth
def get_record(record_id):
    record = CalculationRecord.query.get(record_id)
    if not record:
        return jsonify({"success": False, "error": "记录不存在"}), 404
    if request.current_user.role != "admin" and record.user_id != request.current_user.id:
        return jsonify({"success": False, "error": "无权访问"}), 403
    return jsonify({"success": True, "data": record.to_dict()})


@records_bp.route("/<int:record_id>", methods=["DELETE"])
@require_auth
def delete_record(record_id):
    record = CalculationRecord.query.get(record_id)
    if not record:
        return jsonify({"success": False, "error": "记录不存在"}), 404
    if request.current_user.role != "admin" and record.user_id != request.current_user.id:
        return jsonify({"success": False, "error": "无权删除"}), 403
    db.session.delete(record)
    db.session.commit()
    return jsonify({"success": True})


@records_bp.route("/export", methods=["GET"])
@require_auth
def export_records():
    record_type = request.args.get("type")
    query = CalculationRecord.query
    if request.current_user.role != "admin":
        query = query.filter_by(user_id=request.current_user.id)
    if record_type:
        query = query.filter_by(type=record_type)
    records = query.order_by(CalculationRecord.created_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "类型", "输入数据", "结果", "创建时间"])
    for r in records:
        writer.writerow([r.id, r.type, r.input_data, r.result, r.created_at])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=records.csv"},
    )
