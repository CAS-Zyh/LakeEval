import sys
import os
import time
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, jsonify
from flask_cors import CORS
from config import DATABASE_URI, ALLOWED_ORIGINS, RATE_LIMIT_PER_MINUTE
from .extensions import db


def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024  # 请求体上限 2MB
    # 避免 SQLite 连接池问题（尤其是内存数据库跨线程/多 worker 场景）
    if DATABASE_URI.strip().lower().startswith("sqlite:///"):
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "connect_args": {"check_same_thread": False},
            "pool_pre_ping": True,
        }

    # CORS 白名单：精确域名 + 通配子域（例如 https://*.streamlit.app）
    # Flask-CORS origins 支持字符串列表 + 正则；我们把带 * 的条目编译成 re.compile()
    import re as _re
    def _normalize_origins(raw_list):
        normalized = []
        for o in raw_list:
            if "*" in o:
                pattern = "^" + _re.escape(o).replace(r"\*", r"[^.]+" if o.startswith("*.") else r".*") + "$"
                normalized.append(_re.compile(pattern))
            else:
                normalized.append(o)
        return normalized

    _cors_origins = _normalize_origins(ALLOWED_ORIGINS)
    CORS(app, origins=_cors_origins, supports_credentials=False, resources={r"/*": {"origins": _cors_origins}})

    db.init_app(app)

    # --- IP 速率限制 ---
    _ip_hits = defaultdict(list)

    @app.before_request
    def _rate_limit():
        if request.path.startswith("/static/"):
            return
        ip = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()
        now = time.time()
        window = 60.0
        hits = _ip_hits[ip]
        _ip_hits[ip] = [t for t in hits if now - t < window]
        _ip_hits[ip].append(now)
        if len(_ip_hits[ip]) > RATE_LIMIT_PER_MINUTE:
            return jsonify({
                "success": False,
                "error": "请求过于频繁，请稍后再试",
                "code": "RATE_LIMITED",
            }), 429

    # --- 统一服务状态端点（供前端查询：是否内存模式/版本） ---
    # 暴露两条路径：/api/status（标准 API 前缀）和 /status（启动健康检查裸路径）
    # 两者返回值完全一致，避免不同调用方路径约定不一致造成 404。
    @app.route("/api/status", methods=["GET"])
    @app.route("/status", methods=["GET"])
    def _status():
        from config import DB_EPHEMERAL
        return jsonify({
            "success": True,
            "data": {
                "ok": True,
                "db_ephemeral": DB_EPHEMERAL,
                "db_uri_masked": _mask_uri(DATABASE_URI),
                "server_time": datetime.utcnow().isoformat() + "Z",
            },
        })

    from .routes.auth import auth_bp
    from .routes.tli import tli_bp
    from .routes.bqi import bqi_bp
    from .routes.reduction import reduction_bp
    from .routes.records import records_bp
    from .routes.chat import chat_bp
    from .routes.admin import admin_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(tli_bp, url_prefix="/api/tli")
    app.register_blueprint(bqi_bp, url_prefix="/api/bqi")
    app.register_blueprint(reduction_bp, url_prefix="/api/reduction")
    app.register_blueprint(records_bp, url_prefix="/api/records")
    app.register_blueprint(chat_bp, url_prefix="/api/chat")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")

    # 建表 + 初始化默认管理员（捕获所有异常，保证即便在只读文件系统中服务仍可启动）
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:  # noqa: BLE001 - 启动期任何 DB 问题都不能崩
            app.logger.warning(f"[DB] db.create_all() 跳过（{type(e).__name__}: {str(e)[:120]}）")
        try:
            _init_default_admin()
        except Exception as e:
            app.logger.warning(f"[DB] 默认管理员初始化跳过（{type(e).__name__}: {str(e)[:120]}）")

    return app


def _mask_uri(uri: str) -> str:
    """脱敏数据库连接串，避免泄露密码。"""
    if not uri:
        return ""
    # sqlite 直接返回
    if uri.startswith("sqlite"):
        return uri
    # postgres/mysql: 隐藏 :password@ 中间的密码部分
    import re
    return re.sub(r"://([^:]+):([^@]+)@", r"://\1:***@", uri, count=1)


def _init_default_admin():
    from .models import User
    from config import DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD
    from .safe_db import safe_add

    existing = User.query.filter_by(username=DEFAULT_ADMIN_USERNAME).first()
    if existing:
        return
    admin = User(
        username=DEFAULT_ADMIN_USERNAME,
        role="admin",
        daily_chat_limit=-1,
    )
    admin.set_password(DEFAULT_ADMIN_PASSWORD)
    ok, err = safe_add(admin, commit=True)
    if not ok:
        # 内存数据库中应成功；若失败（只读文件系统），不抛异常，服务仍可启动
        import logging
        logging.getLogger(__name__).warning("默认管理员创建失败：%s", err)


if __name__ == "__main__":
    app = create_app()
    from config import FLASK_PORT, FLASK_HOST
    app.run(debug=True, host=FLASK_HOST, port=FLASK_PORT)
