import json
import requests
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import FLASK_PORT

# 支持环境变量配置 API 地址（分离部署时指向 Render 上的 Flask 后端）
# 本地开发默认 http://127.0.0.1:5001/api
# Streamlit Cloud 部署时设置 API_BASE_URL=https://your-app.onrender.com/api
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
