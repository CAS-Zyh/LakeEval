import streamlit as st


def metric_card(title, value, subtitle=None, color="#1d4ed8"):
    subtitle_html = f'<div style="font-size:0.75rem;color:#9ca3af;margin-top:0.25rem;">{subtitle}</div>' if subtitle else ""
    st.markdown(f"""
    <div class="metric-card">
        <div style="font-size:0.75rem;color:#6b7280;">{title}</div>
        <div style="font-size:1.75rem;font-weight:700;color:{color};">{value}</div>
        {subtitle_html}
    </div>
    """, unsafe_allow_html=True)


def grade_badge(name, color):
    st.markdown(f"""
    <span class="grade-badge" style="background:{color};">{name}</span>
    """, unsafe_allow_html=True)


def section_title(title):
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)


def info_box(text):
    st.markdown(f'<div class="info-box">{text}</div>', unsafe_allow_html=True)


def warning_box(text):
    st.markdown(f'<div class="warning-box">{text}</div>', unsafe_allow_html=True)


def error_box(text):
    st.markdown(f'<div class="error-box">{text}</div>', unsafe_allow_html=True)


def success_box(text):
    st.markdown(f'<div class="success-box">{text}</div>', unsafe_allow_html=True)
