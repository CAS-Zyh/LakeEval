import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import json
import streamlit as st
from ui.theme import apply_theme
from ui.auth import require_auth
from ui.api_client import api
from ui.components.metric_cards import section_title, info_box

apply_theme()
user = require_auth()

st.title("历史记录")

filter_type = st.selectbox("筛选类型", ["全部", "TLI", "BQI", "削减方案"])
type_map = {"全部": None, "TLI": "tli", "BQI": "bqi", "削减方案": "reduction"}

result = api.get("/records", {"type": type_map[filter_type], "limit": 50})

if not result.get("success"):
    st.error(result.get("error", "获取记录失败"))
elif not result["data"]:
    info_box("暂无记录")
else:
    col1, col2 = st.columns([4, 1])
    with col2:
        if st.button("导出 CSV"):
            st.markdown(f"[点击导出](http://127.0.0.1:5001/api/records/export?type={type_map[filter_type] or ''})")

    for record in result["data"]:
        with st.container():
            col1, col2, col3 = st.columns([1, 3, 1])
            with col1:
                type_color = {"tli": "#1d4ed8", "bqi": "#10b981", "reduction": "#8b5cf6"}.get(record["type"], "#6b7280")
                st.markdown(f"""
                <span style="padding:0.25rem 0.75rem;border-radius:4px;
                             background:{type_color}20;color:{type_color};
                             font-size:0.75rem;font-weight:600;">
                    {record["type"].upper()}
                </span>
                """, unsafe_allow_html=True)
            with col2:
                try:
                    parsed = json.loads(record["result"])
                    if record["type"] == "tli":
                        summary = f"TLI={parsed.get('total_tli', 0):.2f} ({parsed.get('grade_name', '-')})"
                    elif record["type"] == "bqi":
                        summary = f"BQI={parsed.get('bqi', 0):.2f} ({parsed.get('grade_name', '-')})"
                    else:
                        summary = f"TLI={parsed.get('tli', 0):.2f}"
                    st.write(summary)
                except:
                    st.write(record["result"][:80])

                st.caption(record["created_at"])

            with col3:
                if st.button("删除", key=f"del_{record['id']}"):
                    del_result = api.delete(f"/records/{record['id']}")
                    if del_result.get("success"):
                        st.rerun()
                    else:
                        st.error(del_result.get("error", "删除失败"))

            st.divider()
