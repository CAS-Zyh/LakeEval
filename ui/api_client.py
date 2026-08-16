import json
import requests
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import FLASK_PORT

# === 自动从 Streamlit Cloud Secrets 中读取覆盖（如果存在）===
# 做法：允许在 share.streamlit.io → App Settings → Secrets 中写
#   api_base_url = "https://xxxx.onrender.com/api"
#   jwt_secret = "..."（或其他 config 环境变量）
# 就会被自动写到 os.environ，与本地开发的 .env 行为保持一致。
def _apply_streamlit_secrets_to_env() -> None:
    try:
        secrets = st.secrets
    except Exception:
        return
    if not secrets:
        return
    # 常见需要覆盖的 key -> 环境变量名；其它 key-value 也会按"原样大写"写入 env
    _mapping = {
        "api_base_url": "API_BASE_URL",
        "jwt_secret": "JWT_SECRET",
        "deepseek_api_key": "DEEPSEEK_API_KEY",
        "deepseek_base_url": "DEEPSEEK_BASE_URL",
        "deepseek_model": "DEEPSEEK_MODEL",
        "flask_host": "FLASK_HOST",
        "flask_port": "FLASK_PORT",
        "database_uri": "DATABASE_URI",
        "allowed_origins": "ALLOWED_ORIGINS",
        "rate_limit_per_minute": "RATE_LIMIT_PER_MINUTE",
        "kb_enabled": "KB_ENABLED",
        "kb_dir": "KB_DIR",
        "guest_daily_chat_limit": "GUEST_DAILY_CHAT_LIMIT",
        "guest_max_tokens": "GUEST_MAX_TOKENS",
        "user_daily_chat_limit": "USER_DAILY_CHAT_LIMIT",
        "default_admin_username": "DEFAULT_ADMIN_USERNAME",
        "default_admin_password": "DEFAULT_ADMIN_PASSWORD",
    }
    for key, value in secrets.items():
        if value is None:
            continue
        env_name = _mapping.get(str(key).lower()) or str(key).upper()
        # 只在用户没设置时才用 Secret 覆盖，避免本地显式环境变量被 Secrets 推翻
        os.environ.setdefault(env_name, str(value))

_apply_streamlit_secrets_to_env()


# 支持环境变量配置 API 地址（分离部署时指向独立后端如 Render）
# 本地 / 单体部署默认 http://127.0.0.1:5001/api
# Streamlit Cloud 单体部署：不需设置 API_BASE_URL Secrets，Flask 会作为子进程本地启动
# Streamlit Cloud 分离部署：在 Secrets 设置 api_base_url=https://your-backend.onrender.com/api
API_BASE_URL = os.getenv("API_BASE_URL", f"http://127.0.0.1:{FLASK_PORT}/api")
BASE_URL = API_BASE_URL


class ApiClient:
    def _headers(self):
        headers = {"Content-Type": "application/json"}
        token = st.session_state.get("token")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def post(self, path, data=None):
        try:
            resp = requests.post(f"{BASE_URL}{path}", json=data, headers=self._headers(), timeout=30)
            return resp.json()
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "无法连接服务器，请确认后端服务已启动"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get(self, path, params=None):
        try:
            resp = requests.get(f"{BASE_URL}{path}", params=params, headers=self._headers(), timeout=30)
            return resp.json()
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "无法连接服务器"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete(self, path):
        try:
            resp = requests.delete(f"{BASE_URL}{path}", headers=self._headers(), timeout=30)
            return resp.json()
        except Exception as e:
            return {"success": False, "error": str(e)}

    def status(self):
        """调用健康检查端点：优先 /api/status；作为兜底再尝试 /status。"""
        candidates = []
        if BASE_URL.endswith("/api"):
            candidates.append(f"{BASE_URL}/status")  # → /api/status
            candidates.append(f"{BASE_URL[:-4]}/status")  # → /status
        else:
            candidates.append(f"{BASE_URL.rstrip('/')}/api/status")
            candidates.append(f"{BASE_URL.rstrip('/')}/status")
        for url in candidates:
            try:
                resp = requests.get(url, headers=self._headers(), timeout=8)
                data = resp.json()
                if data.get("success"):
                    return data.get("data")
            except Exception:
                continue
        return None

    def stream(self, path, data=None):
        try:
            resp = requests.post(
                f"{BASE_URL}{path}", json=data, headers=self._headers(),
                stream=True, timeout=120,
            )
            # 非 200 状态码：后端返回的是普通 JSON 错误（非 SSE 流）
            if resp.status_code != 200:
                try:
                    err = resp.json()
                    yield {"error": err.get("error", f"服务器错误 ({resp.status_code})")}
                except Exception:
                    yield {"error": f"服务器错误 ({resp.status_code})"}
                return
            for line in resp.iter_lines():
                if line:
                    line_str = line.decode("utf-8")
                    if line_str.startswith("data: "):
                        yield json.loads(line_str[6:])
        except requests.exceptions.ConnectionError:
            yield {"error": "无法连接服务器"}
        except Exception as e:
            yield {"error": str(e)}


api = ApiClient()
