import streamlit as st

INDICATOR_CONFIG = {
    "chla": {"label": "Chl-a (μg/L)", "min": 0.1, "max": 200.0, "default": 25.0, "step": 0.1},
    "tp": {"label": "TP (mg/L)", "min": 0.001, "max": 2.0, "default": 0.08, "step": 0.001},
    "tn": {"label": "TN (mg/L)", "min": 0.01, "max": 10.0, "default": 1.5, "step": 0.01},
    "sd": {"label": "SD (m)", "min": 0.05, "max": 10.0, "default": 1.2, "step": 0.05},
    "cod_mn": {"label": "CODMn (mg/L)", "min": 0.1, "max": 20.0, "default": 4.0, "step": 0.1},
}

FACTOR_LABELS = {
    "chla": "Chl-a（藻类响应）",
    "tp": "TP（磷负荷）",
    "tn": "TN（氮负荷）",
    "sd": "SD（透明度/光学响应）",
    "cod_mn": "CODMn（有机物负荷）",
}


def init_indicators():
    if "indicators" not in st.session_state:
        st.session_state.indicators = {
            key: cfg["default"] for key, cfg in INDICATOR_CONFIG.items()
        }


def _precision_of_step(step):
    """根据 step 计算小数位数，用于 round 避免浮点误差。"""
    s = f"{step:.10f}".rstrip("0").rstrip(".")
    if "." in s:
        return len(s.split(".")[1])
    return 0


def _sync_slider(key):
    """滑动栏变化时，按 step 精度 round 后同步到数字输入框。"""
    cfg = INDICATOR_CONFIG[key]
    precision = _precision_of_step(cfg["step"])
    val = round(st.session_state[f"{key}_slider"], precision)
    st.session_state[f"{key}_number"] = val
    st.session_state.indicators[key] = val


def _sync_number(key):
    """数字输入框变化时，按 step 精度 round 后同步到滑动栏。"""
    cfg = INDICATOR_CONFIG[key]
    precision = _precision_of_step(cfg["step"])
    val = round(st.session_state[f"{key}_number"], precision)
    st.session_state[f"{key}_slider"] = val
    st.session_state.indicators[key] = val


def render_indicator_inputs():
    init_indicators()
    st.sidebar.markdown('<div class="section-title">水质指标输入</div>', unsafe_allow_html=True)

    for key, cfg in INDICATOR_CONFIG.items():
        precision = _precision_of_step(cfg["step"])
        col1, col2 = st.sidebar.columns([2.5, 1])
        with col1:
            st.slider(
                cfg["label"],
                min_value=cfg["min"],
                max_value=cfg["max"],
                value=round(st.session_state.indicators[key], precision),
                step=cfg["step"],
                key=f"{key}_slider",
                on_change=_sync_slider,
                args=(key,),
            )
        with col2:
            st.number_input(
                cfg["label"],
                min_value=cfg["min"],
                max_value=cfg["max"],
                value=round(st.session_state.indicators[key], precision),
                step=cfg["step"],
                key=f"{key}_number",
                label_visibility="collapsed",
                on_change=_sync_number,
                args=(key,),
                format="%." + str(precision) + "f",
            )
        st.session_state.indicators[key] = round(
            st.session_state[f"{key}_number"], precision
        )

    is_drinking = st.sidebar.checkbox("饮用水源地", value=True)
    return dict(st.session_state.indicators), is_drinking


def render_reduction_controls():
    st.sidebar.divider()
    st.sidebar.markdown('<div class="section-title">削减参数</div>', unsafe_allow_html=True)

    reduction_pct = st.sidebar.slider(
        "综合削减比例", min_value=0, max_value=80, value=0, step=1,
        help="统一基准削减率，系统会根据限制因子自动差异化分配到 TN/TP/CODMn",
    )

    st.sidebar.caption("ℹ️ Chl-a 由 OECD 响应函数自动推算")
    st.sidebar.caption("ℹ️ 限制因子由 TN/TP 绝对浓度+N:P 比自动诊断")

    # 兼容旧 API 签名：返回 (ratio, chla_mode, chla_link_coeff, target_tli)
    # chla_mode 固定 "auto"，由系统自动决定
    return reduction_pct / 100.0, "auto", 0.6, 50.0


def get_indicators():
    init_indicators()
    return dict(st.session_state.indicators)
