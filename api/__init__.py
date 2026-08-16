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

    # CORS 白名单：只允许指定的前端来源
    CORS(app, origins=ALLOWED_ORIGINS, supports_credentials=False)

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

    with app.app_context():
        db.create_all()
        _init_default_admin()

    return app


def _init_default_admin():
    from .models import User
    from config import DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD
    if not User.query.filter_by(username=DEFAULT_ADMIN_USERNAME).first():
        admin = User(
            username=DEFAULT_ADMIN_USERNAME,
            role="admin",
            daily_chat_limit=-1,
        )
        admin.set_password(DEFAULT_ADMIN_PASSWORD)
        db.session.add(admin)
        db.session.commit()


if __name__ == "__main__":
    app = create_app()
    from config import FLASK_PORT, FLASK_HOST
    app.run(debug=True, host=FLASK_HOST, port=FLASK_PORT)
