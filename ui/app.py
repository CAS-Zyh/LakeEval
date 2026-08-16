import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from ui.theme import apply_theme
from ui.auth import require_auth, current_user, logout_button, login_form
from ui.api_client import api

st.set_page_config(
    page_title="淮河流域中心生态室 - 湖库富营养化评价系统",
    page_icon="🌊",
    layout="wide",
)

apply_theme()

# 侧边栏顶部：机构名称
st.sidebar.markdown("""
<div style="padding:0.75rem 0; text-align:center; border-bottom:1px solid #e5e7eb; margin-bottom:0.5rem;">
    <div style="font-size:1.05rem; font-weight:700; color:#1d4ed8; letter-spacing:0.5px;">
        淮河流域中心生态室
    </div>
    <div style="font-size:0.7rem; color:#9ca3af; margin-top:0.2rem;">
        Huaihe River Basin Ecology Center
    </div>
</div>
""", unsafe_allow_html=True)

user = require_auth()

if user:
    role_label = {"admin": "管理员", "user": "用户", "guest": "游客"}.get(user["role"], user["role"])
    st.sidebar.markdown(f"""
    <div style="padding:0.5rem 0;">
        <strong style="color:#1f2937;">{user['username']}</strong>
        <span style="color:#6b7280;font-size:0.8rem;">（{role_label}）</span>
    </div>
    """, unsafe_allow_html=True)

    # 游客显示登录/注册入口
    if user["role"] == "guest":
        with st.sidebar.expander("登录 / 注册（获取更多额度）"):
            login_form()
    else:
        logout_button()

    st.sidebar.divider()

    st.markdown("""
    <div style="display:flex;align-items:center;justify-content:space-between;
                padding:1rem 1.5rem;background:#fff;border:1px solid #e5e7eb;
                border-radius:8px;margin-bottom:1.5rem;">
        <div>
            <h1 style="margin:0;font-size:1.4rem;color:#1f2937;">
                湖库富营养化动态评价与决策辅助系统
            </h1>
            <p style="margin:0.25rem 0 0 0;font-size:0.8rem;color:#6b7280;">
                Lake Eutrophication Assessment & Decision Support System
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        <div class="metric-card">
            <div style="font-size:0.75rem;color:#6b7280;">计算记录</div>
            <div style="font-size:1.5rem;font-weight:700;color:#1d4ed8;">查看历史</div>
            <div style="font-size:0.75rem;color:#9ca3af;margin-top:0.25rem;">支持TLI/BQI/削减方案</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        usage = api.get("/auth/usage")
        if usage.get("success"):
            data = usage["data"]
            if data["chat_limit"] == -1:
                st.markdown("""
                <div class="metric-card">
                    <div style="font-size:0.75rem;color:#6b7280;">AI对话额度</div>
                    <div style="font-size:1.5rem;font-weight:700;color:#1d4ed8;">无限</div>
                    <div style="font-size:0.75rem;color:#9ca3af;margin-top:0.25rem;">管理员权限</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="metric-card">
                    <div style="font-size:0.75rem;color:#6b7280;">AI对话额度</div>
                    <div style="font-size:1.5rem;font-weight:700;color:#1d4ed8;">{data['remaining']}/{data['chat_limit']}</div>
                    <div style="font-size:0.75rem;color:#9ca3af;margin-top:0.25rem;">今日剩余次数</div>
                </div>
                """, unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div class="metric-card">
            <div style="font-size:0.75rem;color:#6b7280;">功能模块</div>
            <div style="font-size:1.5rem;font-weight:700;color:#1d4ed8;">5个</div>
            <div style="font-size:0.75rem;color:#9ca3af;margin-top:0.25rem;">TLI / BQI / 削减 / 记录 / AI</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <div class="info-box">
        <strong>使用指南：</strong>
        请通过左侧导航栏选择功能页面。
        TLI评价页面输入5项水质指标进行综合评价；
        BQI评价页面输入底栖动物数据进行底栖状况评价；
        削减方案页面进行协同削减模拟和智能方案生成；
        AI助手页面可与DeepSeek进行智能对话，支持湖泊评价数据分析。
    </div>
    """, unsafe_allow_html=True)
