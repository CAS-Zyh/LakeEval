import streamlit as st

THEME_CSS = """
<style>
.stApp {
    background-color: #f8fafc;
}

.main .block-container {
    padding-top: 2rem;
    max-width: 1200px;
}

h1, h2, h3 {
    color: #1f2937 !important;
}

.stSidebar .sidebar-content {
    background-color: #ffffff;
    border-right: 1px solid #e5e7eb;
}

.metric-card {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-left: 4px solid #1d4ed8;
    border-radius: 8px;
    padding: 1rem 1.25rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

.grade-badge {
    display: inline-block;
    padding: 0.375rem 1rem;
    border-radius: 9999px;
    font-size: 0.875rem;
    font-weight: 600;
    color: white;
}

.stButton > button {
    background-color: #1d4ed8;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 0.5rem 1.5rem;
    font-weight: 500;
    transition: all 0.2s;
}

.stButton > button:hover {
    background-color: #1e40af;
    color: white;
}

.stButton > button:disabled {
    background-color: #9ca3af;
    color: white;
}

.stTabs [data-baseweb="tab-list"] {
    border-bottom: 2px solid #e5e7eb;
}

.stTabs [data-baseweb="tab"][aria-selected="true"] {
    border-bottom-color: #1d4ed8;
    color: #1d4ed8;
}

.section-title {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 1.1rem;
    font-weight: 600;
    color: #1f2937;
    margin-bottom: 1rem;
}

.section-title::before {
    content: '';
    width: 4px;
    height: 20px;
    background: #1d4ed8;
    border-radius: 2px;
}

.info-box {
    padding: 1rem;
    border-radius: 8px;
    border-left: 3px solid #3b82f6;
    background: #eff6ff;
    margin: 0.75rem 0;
}

.warning-box {
    padding: 1rem;
    border-radius: 8px;
    border-left: 3px solid #f59e0b;
    background: #fffbeb;
    margin: 0.75rem 0;
}

.error-box {
    padding: 1rem;
    border-radius: 8px;
    border-left: 3px solid #dc2626;
    background: #fef2f2;
    margin: 0.75rem 0;
}

.success-box {
    padding: 1rem;
    border-radius: 8px;
    border-left: 3px solid #16a34a;
    background: #f0fdf4;
    margin: 0.75rem 0;
}
</style>
"""


def apply_theme():
    st.markdown(THEME_CSS, unsafe_allow_html=True)
