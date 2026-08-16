import json
import io
import csv
from flask import Blueprint, request, jsonify, Response
from ..auth import require_auth
from ..models import CalculationRecord
from ..extensions import db
from ..safe_db import safe_commit, safe_delete

records_bp = Blueprint("records", __name__)


@records_bp.route("", methods=["GET"])
@require_auth
def list_records():
    # 游客无持久化记录，返回空列表
    if request.current_user.role == "guest":
        return jsonify({"success": True, "data": []})

    record_type = request.args.get("type")
    limit = min(int(request.args.get("limit", 50)), 200)

    try:
        query = CalculationRecord.query
        if request.current_user.role != "admin":
            query = query.filter_by(user_id=request.current_user.id)
        if record_type:
            query = query.filter_by(type=record_type)
        records = query.order_by(CalculationRecord.created_at.desc()).limit(limit).all()
        return jsonify({"success": True, "data": [r.to_dict() for r in records]})
    except Exception as e:
        return jsonify({"success": True, "data": [], "warn": f"读取失败：{str(e)[:80]}"})


@records_bp.route("/<int:record_id>", methods=["GET"])
@require_auth
def get_record(record_id):
    try:
        record = CalculationRecord.query.get(record_id)
    except Exception as e:
        return jsonify({"success": False, "error": f"查询失败：{str(e)[:120]}"}), 503
    if not record:
        return jsonify({"success": False, "error": "记录不存在"}), 404
    if request.current_user.role != "admin" and record.user_id != request.current_user.id:
        return jsonify({"success": False, "error": "无权访问"}), 403
    return jsonify({"success": True, "data": record.to_dict()})


@records_bp.route("/<int:record_id>", methods=["DELETE"])
@require_auth
def delete_record(record_id):
    try:
        record = CalculationRecord.query.get(record_id)
    except Exception as e:
        return jsonify({"success": False, "error": f"查询失败：{str(e)[:120]}"}), 503
    if not record:
        return jsonify({"success": False, "error": "记录不存在"}), 404
    if request.current_user.role != "admin" and record.user_id != request.current_user.id:
        return jsonify({"success": False, "error": "无权删除"}), 403
    ok, err = safe_delete(record)
    if not ok:
        return jsonify({"success": False, "error": err, "code": "DB_WRITE_FAILED"}), 503
    return jsonify({"success": True})


@records_bp.route("/export", methods=["GET"])
@require_auth
def export_records():
    """CSV 导出：使用 io.StringIO 纯内存生成，不落盘。"""
    record_type = request.args.get("type")
    try:
        query = CalculationRecord.query
        if request.current_user.role != "admin":
            query = query.filter_by(user_id=request.current_user.id)
        if record_type:
            query = query.filter_by(type=record_type)
        records = query.order_by(CalculationRecord.created_at.desc()).all()
    except Exception as e:
        return jsonify({"success": False, "error": f"读取失败：{str(e)[:120]}"}), 503

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
