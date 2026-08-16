import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
from ui.theme import apply_theme
from ui.auth import require_auth
from ui.api_client import api
from ui.components.sidebar import render_indicator_inputs, FACTOR_LABELS
from ui.components.metric_cards import metric_card, grade_badge, section_title, info_box, warning_box, success_box, error_box
from ui.components.charts import render_function_curves, render_contribution_bars

apply_theme()
user = require_auth()

st.title("TLI 综合营养状态评价")

values, is_drinking = render_indicator_inputs()

if st.button("计算 TLI", type="primary", use_container_width=True):
    result = api.post("/tli/calculate", values)
    if result.get("success"):
        data = result["data"]
        st.session_state.last_tli_result = data
        st.session_state.last_values = values
    else:
        st.error(result.get("error", "计算失败"))

result = st.session_state.get("last_tli_result")
if result:
    col1, col2 = st.columns([1, 2])

    with col1:
        section_title("综合评价")
        metric_card(
            "综合营养状态指数",
            f"{result['total_tli']:.2f}",
            f"TLI (Σ)",
            result.get("grade_color", "#1d4ed8"),
        )
        grade_badge(result.get("grade_name", ""), result.get("grade_color", ""))
        st.caption("权重：Chl-a=0.2662 | TN=0.1790 | TP=0.1878 | SD=0.1834 | CODMn=0.1834")

    with col2:
        section_title("单项指标 TLI 值")
        cols = st.columns(5)
        indicator_colors = {"chla": "#1d4ed8", "tp": "#f59e0b", "tn": "#10b981", "sd": "#6366f1", "cod_mn": "#8b5cf6"}
        for idx, key in enumerate(["chla", "tp", "tn", "sd", "cod_mn"]):
            with cols[idx]:
                st.metric(
                    key.upper(),
                    f"{result['single_tli'][key]:.1f}",
                    f"权重 {result['weights'][key]:.4f}",
                )

    st.divider()
    section_title("限制因子诊断")

    n_p_ratio = values["tn"] / max(values["tp"], 1e-9)
    auto_pollutant = max(result["contributions"], key=result["contributions"].get)
    main_mode = st.radio("识别模式", ["自动识别", "手动指定"], horizontal=True)
    if main_mode == "自动识别":
        main_pollutant = auto_pollutant
    else:
        main_pollutant = st.selectbox("选择限制因子", list(FACTOR_LABELS.keys()),
                                       format_func=lambda x: FACTOR_LABELS[x])

    main_rate = result["contribution_rate"].get(main_pollutant, 0.0) * 100
    info_box(f"**N:P 质量比** = {n_p_ratio:.2f} {'（磷限制）' if n_p_ratio > 16 else '（氮限制）'}")
    warning_box(f"**主要限制因子**：{FACTOR_LABELS[main_pollutant]}，加权贡献占比 **{main_rate:.1f}%**")

    st.plotly_chart(render_contribution_bars(result["contribution_rate"]), use_container_width=True)

    st.divider()
    section_title("目标倒推模拟（智能化反推）")

    target_tli = st.number_input("目标综合 TLI", 10.0, 100.0, 50.0, 1.0)
    if st.button("执行目标倒推"):
        back_result = api.post("/tli/back_calculate", {
            **values, "target_total_tli": target_tli, "main_pollutant": main_pollutant,
        })
        if back_result.get("success"):
            bd = back_result["data"]
            target_c = bd["target_concentration"]
            current_c = values[main_pollutant]

            unit = {"chla": "μg/L", "tp": "mg/L", "tn": "mg/L", "cod_mn": "mg/L", "sd": "m"}[main_pollutant]
            success_box(
                f"保持其余指标不变时，**{FACTOR_LABELS[main_pollutant]}** 需调整至约 "
                f"**{target_c:.4g} {unit}**（对应 TLI({main_pollutant})={bd['target_single_tli']:.2f}）"
            )

            if main_pollutant == "sd":
                improve_pct = (target_c - current_c) / max(current_c, 1e-9) * 100
                info_box(f"相对当前值 {current_c:.4g} {unit}，需提升约 **{improve_pct:.1f}%**")
            else:
                reduce_pct = (current_c - target_c) / max(current_c, 1e-9) * 100
                info_box(f"相对当前值 {current_c:.4g} {unit}，需削减约 **{reduce_pct:.1f}%**")
        else:
            error_box(back_result.get("error", "倒推失败"))

    st.divider()
    section_title("交互式函数图")
    st.plotly_chart(render_function_curves(values), use_container_width=True)

    if is_drinking and result["total_tli"] > 50:
        error_box(f"⚠️ 饮用水源地预警：综合 TLI = {result['total_tli']:.2f}，已超过中营养阈值，建议优先削减外源负荷")

    if st.button("发送到 AI 助手"):
        st.session_state.ai_context = {
            "total_tli": result["total_tli"],
            "grade_name": result.get("grade_name"),
            "single_tli": result["single_tli"],
            "contribution_rate": result["contribution_rate"],
        }
        success_box("已附加评价数据到 AI 助手，可在 AI 助手页面进行智能分析")
