import jwt
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import request, jsonify
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import JWT_SECRET, JWT_EXPIRY_HOURS, GUEST_TOKEN_EXPIRY_HOURS
from .models import User


def generate_token(user: User) -> str:
    payload = {
        "user_id": user.id,
        "username": user.username,
        "role": user.role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def generate_guest_token(ip: str) -> str:
    payload = {
        "role": "guest",
        "ip": ip,
        "exp": datetime.now(timezone.utc) + timedelta(hours=GUEST_TOKEN_EXPIRY_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


class GuestUser:
    """模拟用户对象，供 guest 角色使用。"""
    def __init__(self, ip: str):
        self.id = None
        self.username = "游客"
        self.role = "guest"
        self.ip = ip
        self.daily_chat_limit = None
        self.is_active = True

    def to_dict(self):
        return {
            "id": None,
            "username": "游客",
            "role": "guest",
            "daily_chat_limit": None,
            "is_active": True,
        }


def get_client_ip() -> str:
    """获取客户端真实 IP（支持反向代理）。"""
    if request.headers.get("X-Forwarded-For"):
        return request.headers["X-Forwarded-For"].split(",")[0].strip()
    if request.headers.get("X-Real-IP"):
        return request.headers["X-Real-IP"].strip()
    return request.remote_addr or "0.0.0.0"


def get_current_user():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    payload = decode_token(token)
    if not payload:
        return None

    if payload.get("role") == "guest":
        return GuestUser(payload.get("ip", "0.0.0.0"))

    user = User.query.get(payload.get("user_id"))
    if not user or not user.is_active:
        return None
    return user


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({"success": False, "error": "未登录或登录已过期"}), 401
        request.current_user = user
        return f(*args, **kwargs)
    return decorated


def require_role(roles: list):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({"success": False, "error": "未登录或登录已过期"}), 401
            if user.role not in roles:
                return jsonify({"success": False, "error": "权限不足"}), 403
            request.current_user = user
            return f(*args, **kwargs)
        return decorated
    return decorator
