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
_SECRETS_MAPPING = {
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

_secrets_applied = False

def _apply_streamlit_secrets_to_env() -> None:
    """延迟读取 Streamlit Secrets 并写入 os.environ。

    重要：本函数不能在 import-time 直接调用！
    因为 st.secrets 在 Streamlit 启动早期（st.set_page_config 之前）不可用，
    会抛 "StreamlitAPIException" 或导致脚本卡死黑屏。
    改为在 ApiClient 第一次真正发起请求时才懒加载。
    """
    global _secrets_applied
    if _secrets_applied:
        return
    _secrets_applied = True
    try:
        secrets = st.secrets
    except Exception:
        return
    if not secrets:
        return
    for key, value in secrets.items():
        if value is None:
            continue
        env_name = _SECRETS_MAPPING.get(str(key).lower()) or str(key).upper()
        # 只在用户没设置时才用 Secret 覆盖，避免本地显式环境变量被 Secrets 推翻
        os.environ.setdefault(env_name, str(value))


def _get_base_url() -> str:
    """延迟计算 BASE_URL，确保 Secrets 已先加载到 os.environ。"""
    _apply_streamlit_secrets_to_env()
    return os.getenv("API_BASE_URL", f"http://127.0.0.1:{FLASK_PORT}/api")


BASE_URL = None  # 延迟初始化，避免 import-time 调用 st.secrets 导致黑屏


class ApiClient:
    def _headers(self):
        headers = {"Content-Type": "application/json"}
        token = st.session_state.get("token")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def post(self, path, data=None):
        try:
            resp = requests.post(f"{_get_base_url()}{path}", json=data, headers=self._headers(), timeout=30)
            return resp.json()
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "无法连接服务器，请确认后端服务已启动"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get(self, path, params=None):
        try:
            resp = requests.get(f"{_get_base_url()}{path}", params=params, headers=self._headers(), timeout=30)
            return resp.json()
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "无法连接服务器"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete(self, path):
        try:
            resp = requests.delete(f"{_get_base_url()}{path}", headers=self._headers(), timeout=30)
            return resp.json()
        except Exception as e:
            return {"success": False, "error": str(e)}

    def status(self):
        """调用健康检查端点：优先 /api/status；作为兜底再尝试 /status。"""
        base = _get_base_url()
        candidates = []
        if base.endswith("/api"):
            candidates.append(f"{base}/status")  # → /api/status
            candidates.append(f"{base[:-4]}/status")  # → /status
        else:
            candidates.append(f"{base.rstrip('/')}/api/status")
            candidates.append(f"{base.rstrip('/')}/status")
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
                f"{_get_base_url()}{path}", json=data, headers=self._headers(),
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
