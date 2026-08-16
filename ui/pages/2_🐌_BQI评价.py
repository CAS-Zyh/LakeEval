import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
from ui.theme import apply_theme
from ui.auth import require_auth
from ui.api_client import api
from ui.components.metric_cards import metric_card, grade_badge, section_title, info_box, success_box, error_box

apply_theme()
user = require_auth()

st.title("BQI 底栖状况指数评价")

species_result = api.get("/bqi/species")
species_list = species_result.get("data", []) if species_result.get("success") else []

section_title("底栖动物种类与数量")
st.caption("BQI = Σ(Si × ni) / N，其中 Si 为指示生物质量常数，ni 为个体数，N 为总个体数")

if "bqi_counts" not in st.session_state:
    st.session_state.bqi_counts = {}

cols_per_row = 4
for i in range(0, len(species_list), cols_per_row):
    cols = st.columns(cols_per_row)
    for j, species in enumerate(species_list[i:i+cols_per_row]):
        with cols[j]:
            val = st.number_input(
                f"{species['name']} (Si={species['si']})",
                min_value=0, max_value=1000, value=0, step=1,
                key=f"bqi_{species['name']}",
            )
            if val > 0:
                st.session_state.bqi_counts[species["name"]] = val
            elif species["name"] in st.session_state.bqi_counts:
                del st.session_state.bqi_counts[species["name"]]

if st.button("计算 BQI", type="primary", use_container_width=True):
    counts = {k: v for k, v in st.session_state.bqi_counts.items() if v > 0}
    if not counts:
        st.warning("请至少输入一种底栖动物的数量")
    else:
        result = api.post("/bqi/calculate", {"species_counts": counts})
        if result.get("success"):
            data = result["data"]
            st.session_state.last_bqi_result = data
        else:
            st.error(result.get("error", "计算失败"))

result = st.session_state.get("last_bqi_result")
if result:
    st.divider()
    section_title("BQI 评价结果")

    col1, col2 = st.columns([1, 2])
    with col1:
        metric_card("底栖状况指数", f"{result['bqi']:.2f}", f"总个体数: {result['total_count']}")
        grade_badge(result["grade_name"], result["grade_color"])

    with col2:
        section_title("物种分布")
        total = result["total_count"]
        for species, count in sorted(result["species_counts"].items(), key=lambda x: x[1], reverse=True):
            pct = count / total * 100
            st.write(f"{species}: {count} 个体 ({pct:.1f}%)")
            st.progress(count / total)

    if result["bqi"] < 2:
        error_box(f"⚠️ BQI 预警：底栖状况为「{result['grade_name']}」，建议加强污染源管控和生态修复措施")
    elif result["bqi"] >= 4:
        success_box(f"✅ BQI 优良：底栖状况为「{result['grade_name']}」，水体生态状况良好")

    if st.button("发送到 AI 助手"):
        st.session_state.ai_context = {
            "bqi": result["bqi"],
            "grade_name": result["grade_name"],
            "total_count": result["total_count"],
        }
        success_box("已附加 BQI 数据到 AI 助手")
