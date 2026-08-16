import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
from ui.theme import apply_theme
from ui.auth import require_auth
from ui.api_client import api
from ui.components.sidebar import render_indicator_inputs, render_reduction_controls, FACTOR_LABELS
from ui.components.metric_cards import (
    metric_card, section_title, info_box, success_box, warning_box, error_box,
)
from ui.components.charts import render_radar_chart

apply_theme()
user = require_auth()

st.title("协同削减情景与智能方案")

values, _ = render_indicator_inputs()
reduction_ratio, chla_mode, chla_link_coeff, _ = render_reduction_controls()

# ========== 营养盐限制因子诊断（独立显示在主区域顶部） ==========
diag_result = api.post("/reduction/diagnose", values)
limitation = diag_result.get("data") if diag_result.get("success") else None

st.divider()
section_title("🩺 营养盐限制因子诊断")

if limitation:
    # 限制类型颜色
    type_color = {
        "saturated": "#dc2626",   # 红：过饱和
        "n_limited": "#f59e0b",   # 橙：氮限制
        "p_limited": "#8b5cf6",   # 紫：磷限制
        "co_limited": "#10b981",  # 绿：协同
    }.get(limitation["type"], "#1d4ed8")

    col_d1, col_d2, col_d3, col_d4 = st.columns(4)
    with col_d1:
        metric_card("限制类型", limitation["label"], color=type_color)
    with col_d2:
        if limitation.get("np_ratio") is not None:
            metric_card("N:P 质量比", f"{limitation['np_ratio']:.2f}",
                         color=type_color)
        else:
            metric_card("N:P 质量比", "—", color=type_color)
    with col_d3:
        metric_card("TN", f"{limitation['tn']:.3f} mg/L",
                     color="#dc2626" if limitation['tn'] > 1.5 else "#10b981")
    with col_d4:
        metric_card("TP", f"{limitation['tp']:.4f} mg/L",
                     color="#dc2626" if limitation['tp'] > 0.1 else "#10b981")

    # 详细描述
    if limitation["type"] == "saturated":
        warning_box("⚠️ " + limitation["description"])
    else:
        info_box("💡 " + limitation["description"])

    # 阈值参考
    with st.expander("📖 阈值标准说明（点击展开）"):
        st.markdown(f"""
        **第一步：绝对浓度阈值过滤（OECD 标准）**
        - TP > {limitation['thresholds']['tp_saturation']} mg/L 或 TN > {limitation['thresholds']['tn_saturation']} mg/L → 营养盐过饱和
        - 过饱和时藻类生长主要受光照、温度等综合因素制约，**N:P 比值失去生态学意义**

        **第二步：低浓度区精细诊断（Forsberg 比值判据）**
        - N:P 质量比 < {limitation['thresholds']['np_n_limit']}（原子比 < 10）→ 氮限制
        - N:P 质量比 > {limitation['thresholds']['np_p_limit']}（原子比 > 20）→ 磷限制
        - {limitation['thresholds']['np_n_limit']} ≤ N:P ≤ {limitation['thresholds']['np_p_limit']}（原子比 10~20）→ 氮磷协同限制

        **削减策略权重**（基于限制因子差异化分配）
        - 营养盐过饱和：TN/TP/CODMn 统一按基准比例削减（综合措施）
        - 氮限制：TN ×1.5、TP ×0.7（参考滇池 AEM3D 研究：TN 需 50% 见效）
        - 磷限制：TP ×1.5、TN ×0.7（参考滇池：TP 25% 即见效）
        - 协同限制：TN/TP 同步按基准比例削减
        """)
else:
    st.warning("诊断接口异常，请检查后端服务")

st.divider()
section_title("🎯 目标削减计算（智能约束）")

col_t1, col_t2 = st.columns([1.3, 1])
with col_t1:
    target_tli = st.number_input(
        "🎯 目标综合 TLI", 10.0, 100.0, 50.0, 1.0,
        help="系统将根据限制因子自动反推差异化的削减方案（考虑工程实务边界）",
    )
with col_t2:
    st.caption("")
    st.caption("模式：智能方案（自动诊断 + 差异化削减）")
    st.caption("Chl-a：OECD 对数线性响应函数自动推算")

if st.button("反推削减方案并预览效果", type="primary", use_container_width=True):
    # Step 1: build_smart_scheme 生成智能方案
    plan_result = api.post("/reduction/smart", {
        **values,
        "target_total_tli": target_tli,
        "chla_mode": "auto",
        "chla_link_coeff": 0.6,
    })
    if not plan_result.get("success"):
        error_box(plan_result.get("error", "方案生成失败"))
    else:
        plan = plan_result["data"]
        ratio = plan.get("ratio", 0)
        # Step 2: 用该比例跑 collaborative，获取完整雷达图和单因子TLI
        collab_result = api.post("/reduction/collaborative", {
            **values,
            "reduction_ratio": ratio,
            "chla_mode": "auto",
            "chla_link_coeff": 0.6,
            "target_total_tli": target_tli,
        })
        if collab_result.get("success"):
            st.session_state.last_reduction_result = collab_result["data"]
            st.session_state.last_smart_plan = plan
            st.session_state.last_reduction_mode = f"目标TLI={target_tli:.0f}（{plan.get('limitation', {}).get('label', '')}）"
            st.session_state.last_input_values = values
        else:
            error_box(collab_result.get("error", "效果计算失败"))

# ========== 结果展示 ==========
result = st.session_state.get("last_reduction_result")
plan = st.session_state.get("last_smart_plan")
mode_label = st.session_state.get("last_reduction_mode", "")
last_values = st.session_state.get("last_input_values", values)

if result and plan:
    section_title(f"削减效果对比（{mode_label}）")

    # --- 总览指标 ---
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("当前综合 TLI", f"{result['current_tli']:.2f}")
    with col2:
        delta = result["delta"]
        delta_str = f"{'↓' if delta < 0 else '↑'} {abs(delta):.2f}"
        metric_card("削减后 TLI", f"{result['simulated_tli']:.2f}", delta_str,
                     "#16a34a" if delta < 0 else "#dc2626")
    with col3:
        grade_color = result.get("grade_color", "#1d4ed8")
        metric_card("削减后等级", result.get("grade_name", ""), color=grade_color)
    with col4:
        metric_card("统一削减率", f"{plan['ratio'] * 100:.1f}%",
                    color="#1d4ed8")

    st.divider()

    # --- 雷达图 ---
    section_title("雷达图对比（单项 TLI）")
    current_profile = [result["current_single_tli"][k] for k in ["chla", "tp", "tn", "sd", "cod_mn"]]
    sim_profile = [result["simulated_single_tli"][k] for k in ["chla", "tp", "tn", "sd", "cod_mn"]]
    st.plotly_chart(render_radar_chart(current_profile, sim_profile), use_container_width=True)

    # --- 关键削减因子 + 削减量 ---
    st.divider()
    section_title("关键削减因子与削减量分析")

    sim_values = result["simulated_values"]
    keys_cn = [
        ("tn", "TN（总氮）", "mg/L"),
        ("tp", "TP（总磷）", "mg/L"),
        ("cod_mn", "CODMn（高锰酸盐指数）", "mg/L"),
        ("sd", "SD（透明度）", "m"),
        ("chla", "Chl-a（叶绿素a）", "μg/L"),
    ]

    # 计算削减量（绝对值差）与削减比例
    factor_rows = []
    for k, cn, unit in keys_cn:
        cur = last_values[k]
        aft = sim_values[k]
        if k == "sd":
            abs_change = aft - cur
            pct = abs_change / max(cur, 1e-9) * 100
            change_dir = "提升" if abs_change >= 0 else "下降"
        elif k == "chla":
            abs_change = cur - aft
            pct = abs_change / max(cur, 1e-9) * 100
            change_dir = "下降" if abs_change >= 0 else "上升"
        else:
            abs_change = cur - aft
            pct = abs_change / max(cur, 1e-9) * 100
            change_dir = "削减" if abs_change >= 0 else "上升"
        factor_rows.append({
            "key": k, "name": cn, "unit": unit,
            "current": cur, "after": aft,
            "abs_change": abs(abs_change),
            "pct": abs(pct),
            "change_dir": change_dir,
            "signed_abs": abs_change if k != "sd" else -abs_change,
        })

    # 关键削减因子：按 "削减绝对量占当前值比例"（即削减比例%）排序，取前 2 名
    # 对于常规污染指标（tn/tp/cod_mn/chla）看削减%，sd看提升%
    cut_ranked = sorted(
        [r for r in factor_rows if r["key"] in ("tn", "tp", "cod_mn", "chla")],
        key=lambda r: r["pct"],
        reverse=True,
    )
    sd_row = next(r for r in factor_rows if r["key"] == "sd")

    # 关键因子展示
    kc1, kc2, kc3 = st.columns(3)
    with kc1:
        if cut_ranked:
            f = cut_ranked[0]
            metric_card(
                "🥇 关键削减因子 #1",
                f['name'].split('（')[0],
                f"{f['change_dir']} {f['pct']:.1f}%",
                "#dc2626",
            )
    with kc2:
        if len(cut_ranked) > 1:
            f = cut_ranked[1]
            metric_card(
                "🥈 关键削减因子 #2",
                f['name'].split('（')[0],
                f"{f['change_dir']} {f['pct']:.1f}%",
                "#f59e0b",
            )
    with kc3:
        metric_card(
            "💡 透明度",
            "SD",
            f"{sd_row['change_dir']} {sd_row['pct']:.1f}%",
            "#6366f1",
        )

    info_box(
        f"**关键削减策略**：以 **{cut_ranked[0]['name'] if cut_ranked else 'TN'}** "
        f"（削减 {cut_ranked[0]['pct']:.1f}%）为首要抓手，"
        f"配合 **{cut_ranked[1]['name'] if len(cut_ranked) > 1 else 'TP'}** "
        f"（削减 {cut_ranked[1]['pct']:.1f}%）协同控制，"
        f"同步提升水体透明度 SD {sd_row['pct']:.1f}%。"
    )

    # --- 指标浓度变化 & 削减量表 ---
    section_title("指标浓度与削减量明细")
    table_data = []
    for r in factor_rows:
        cur, aft, unit = r["current"], r["after"], r["unit"]
        delta_abs = r["abs_change"]
        if r["key"] == "sd":
            change_str = f"{'↑' if (aft - cur) >= 0 else '↓'} {delta_abs:.4g} {unit}（{r['pct']:.1f}%）"
        else:
            change_str = f"{'↓' if (cur - aft) >= 0 else '↑'} {delta_abs:.4g} {unit}（{r['pct']:.1f}%）"
        table_data.append({
            "污染物因子": r["name"],
            "单位": unit,
            "当前浓度": f"{cur:.4g}",
            "削减后浓度": f"{aft:.4g}",
            "削减量/提升量": change_str,
        })
    st.table(table_data)

    # 削减压力分布
    pressure = {
        "TN": plan["cuts"].get("tn", 0),
        "TP": plan["cuts"].get("tp", 0),
        "CODMN": plan["cuts"].get("cod_mn", 0),
        "SD提升": plan["cuts"].get("sd", 0),
    }
    info_box("削减压力分布：" + "，".join([f"**{k}** {v:.1f}%" for k, v in pressure.items()]))

    st.divider()

    # --- 智能方案详情 & 约束提示 ---
    section_title("智能治理方案详情（约束边界内）")
    success_box(plan["summary"] + " " + plan.get("detail", ""))

    # 限制因子策略建议
    if plan.get("strategy"):
        info_box("🎯 **针对性策略建议**：" + plan["strategy"])

    cols = st.columns(5)
    cut_labels = {"tn": "TN 削减", "tp": "TP 削减", "cod_mn": "CODMn 削减",
                  "sd": "SD 提升", "chla": "Chl-a 变化"}
    for idx, key in enumerate(["tn", "tp", "cod_mn", "sd", "chla"]):
        with cols[idx]:
            cut_val = plan["cuts"].get(key, 0)
            st.metric(cut_labels[key], f"{cut_val:+.1f}%")

    pv = plan["values"]
    st.write(
        f"🎯 工程控制目标："
        f"TN ≤ {pv['tn']:.3f} mg/L | "
        f"TP ≤ {pv['tp']:.4f} mg/L | "
        f"CODMn ≤ {pv['cod_mn']:.3f} mg/L | "
        f"Chl-a ≤ {pv['chla']:.2f} μg/L | "
        f"SD ≥ {pv['sd']:.2f} m"
    )

    if not plan["reachable"]:
        warning_box(
            "⚠️ 仅靠当前协同削减（约束边界内）无法达到目标 TLI。"
            "建议：① 叠加生态修复（如浮岛、底质疏浚、鱼类调控）以改善 Chl-a 和 SD；"
            "② 进一步降低污染源（如提标改造尾水、削减面源负荷）。"
        )

    hit_keys = [k.upper() for k, v in plan["constraints_hit"].items() if v]
    if hit_keys:
        info_box(
            f"🔒 已触发实务边界约束：{', '.join(hit_keys)} 已达到工程可实现下限/上限。"
            "（例如 TP 工程下限约 0.005 mg/L，SD 上限约 10 m）"
        )

    if st.button("发送到 AI 助手"):
        st.session_state.ai_context = {
            "ratio": plan["ratio"],
            "tli": plan["tli"],
            "cuts": plan["cuts"],
            "values": plan["values"],
            "reachable": plan["reachable"],
            "target_tli": target_tli,
        }
        success_box("已附加方案数据到 AI 助手，可在 AI 助手页面获取针对性治理建议")
