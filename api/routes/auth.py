from datetime import datetime
from flask import Blueprint, request, jsonify
from ..models import User
from ..auth import generate_token, generate_guest_token, require_auth, get_client_ip
from ..extensions import db

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.json or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username or not password:
        return jsonify({"success": False, "error": "用户名和密码不能为空"}), 400
    if len(username) < 3:
        return jsonify({"success": False, "error": "用户名至少3个字符"}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"success": False, "error": "用户名已存在"}), 409

    user = User(username=username, role="user", daily_chat_limit=10)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    token = generate_token(user)
    return jsonify({"success": True, "data": {"token": token, "user": user.to_dict()}}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.json or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({"success": False, "error": "用户名或密码错误"}), 401
    if not user.is_active:
        return jsonify({"success": False, "error": "账号已被禁用"}), 403

    user.last_login_at = datetime.utcnow()
    db.session.commit()
    token = generate_token(user)
    return jsonify({"success": True, "data": {"token": token, "user": user.to_dict()}})


@auth_bp.route("/guest_token", methods=["POST"])
def guest_token():
    """为游客签发临时 token，按 IP 限制用量。"""
    ip = get_client_ip()
    token = generate_guest_token(ip)
    return jsonify({"success": True, "data": {
        "token": token,
        "user": {"username": "游客", "role": "guest", "ip": ip},
    }})


@auth_bp.route("/me", methods=["GET"])
@require_auth
def me():
    return jsonify({"success": True, "data": request.current_user.to_dict()})


@auth_bp.route("/usage", methods=["GET"])
@require_auth
def usage():
    from ..services.usage import get_today_usage, get_guest_usage
    user = request.current_user
    if user.role == "guest":
        return jsonify({"success": True, "data": get_guest_usage(user.ip)})
    return jsonify({"success": True, "data": get_today_usage(user.id)})
