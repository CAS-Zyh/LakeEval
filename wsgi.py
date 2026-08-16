"""Render 部署用 WSGI 入口：只启动 Flask 后端，不启动 Streamlit。

本地开发用 `python run.py`（同时启动 Flask + Streamlit）。
Render 部署用 `gunicorn wsgi:app`（只启动 Flask）。
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api import create_app

app = create_app()

if __name__ == "__main__":
    from config import FLASK_PORT, FLASK_HOST
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False)
