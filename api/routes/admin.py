from flask import Blueprint, request, jsonify
from ..auth import require_role
from ..models import User, CalculationRecord, ChatHistory
from ..extensions import db

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/users", methods=["GET"])
@require_role(["admin"])
def list_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify({"success": True, "data": [u.to_dict() for u in users]})


@admin_bp.route("/users/<int:user_id>", methods=["PATCH"])
@require_role(["admin"])
def update_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"success": False, "error": "用户不存在"}), 404
    data = request.json or {}
    if "role" in data:
        user.role = data["role"]
        user.daily_chat_limit = -1 if data["role"] == "admin" else (0 if data["role"] == "guest" else 10)
    if "daily_chat_limit" in data:
        user.daily_chat_limit = int(data["daily_chat_limit"])
    if "is_active" in data:
        user.is_active = bool(data["is_active"])
    db.session.commit()
    return jsonify({"success": True, "data": user.to_dict()})


@admin_bp.route("/users/<int:user_id>", methods=["DELETE"])
@require_role(["admin"])
def delete_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"success": False, "error": "用户不存在"}), 404
    if user.role == "admin":
        return jsonify({"success": False, "error": "不能删除管理员账号"}), 400
    db.session.delete(user)
    db.session.commit()
    return jsonify({"success": True})


@admin_bp.route("/stats", methods=["GET"])
@require_role(["admin"])
def stats():
    total_users = User.query.count()
    total_records = CalculationRecord.query.count()
    total_chats = ChatHistory.query.count()
    return jsonify({"success": True, "data": {
        "total_users": total_users,
        "total_records": total_records,
        "total_chats": total_chats,
    }})
