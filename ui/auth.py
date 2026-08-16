import streamlit as st
from .api_client import api


def _ensure_guest_token():
    """如果没有 token，自动获取游客 token。"""
    if not st.session_state.get("token"):
        resp = api.post("/auth/guest_token")
        if resp.get("success"):
            st.session_state.token = resp["data"]["token"]
            st.session_state.user = resp["data"]["user"]


def login_form():
    st.markdown('<div class="section-title">登录 / 注册</div>', unsafe_allow_html=True)

    tab_login, tab_register = st.tabs(["登录", "注册"])

    with tab_login:
        with st.form("login_form"):
            username = st.text_input("用户名", key="login_username")
            password = st.text_input("密码", type="password", key="login_password")
            submitted = st.form_submit_button("登录", use_container_width=True)

            if submitted:
                if not username or not password:
                    st.error("请输入用户名和密码")
                else:
                    result = api.post("/auth/login", {"username": username, "password": password})
                    if result.get("success"):
                        st.session_state.token = result["data"]["token"]
                        st.session_state.user = result["data"]["user"]
                        st.success("登录成功")
                        st.rerun()
                    else:
                        st.error(result.get("error", "登录失败"))

    with tab_register:
        with st.form("register_form"):
            username = st.text_input("用户名", key="reg_username")
            password = st.text_input("密码", type="password", key="reg_password")
            submitted = st.form_submit_button("注册", use_container_width=True)

            if submitted:
                if not username or not password:
                    st.error("请输入用户名和密码")
                elif len(username) < 3:
                    st.error("用户名至少3个字符")
                else:
                    result = api.post("/auth/register", {"username": username, "password": password})
                    if result.get("success"):
                        st.session_state.token = result["data"]["token"]
                        st.session_state.user = result["data"]["user"]
                        st.success("注册成功，已自动登录")
                        st.rerun()
                    else:
                        st.error(result.get("error", "注册失败"))

    st.info("注册后可享更多 AI 对话额度（10次/天）。默认管理员：admin / admin123")


def require_auth():
    _ensure_guest_token()
    return st.session_state.get("user")


def require_role(roles):
    user = require_auth()
    if user and user.get("role") not in roles:
        st.warning("权限不足，无法访问此页面")
        st.stop()
    return user


def current_user():
    return st.session_state.get("user")


def logout_button():
    if st.session_state.get("token"):
        role = st.session_state.get("user", {}).get("role", "")
        label = "退出登录" if role != "guest" else "刷新游客会话"
        if st.sidebar.button(label):
            st.session_state.pop("token", None)
            st.session_state.pop("user", None)
            st.rerun()
