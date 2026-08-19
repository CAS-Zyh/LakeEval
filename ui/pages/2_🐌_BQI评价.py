import sys
import os

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _PROJECT_ROOT)
# 本地依赖目录（沙箱无法写入系统 site-packages 时，matplotlib 安装于此）
sys.path.append(os.path.join(_PROJECT_ROOT, ".vendor"))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from ui.theme import apply_theme
from ui.auth import require_auth
from ui.api_client import api
from ui.components.metric_cards import metric_card, section_title, info_box, success_box, error_box, warning_box

apply_theme()
user = require_auth()


def _configure_matplotlib():
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "SimSun", "Arial Unicode MS", "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False


def render_bqi_score_chart(summary_df):
    """图 A：各点位 BQI 得分柱状图。"""
    _configure_matplotlib()
    sites = summary_df["样点"].astype(str).tolist()
    bqi = summary_df["BQI 得分 (100分制)"].astype(float).tolist()

    x = np.arange(len(sites))
    fig, ax = plt.subplots(figsize=(max(6.0, len(sites) * 1.3), 5.0))
    bars = ax.bar(x, bqi, width=0.5, color="#4ba3e3")

    ax.set_xlabel("点位")
    ax.set_ylabel("BQI 得分")
    ax.set_title("图 A：各点位 BQI 得分")
    ax.set_xticks(x)
    ax.set_xticklabels(sites)
    ax.set_ylim(0, 100)

    for bar in bars:
        height = bar.get_height()
        ax.annotate(
            f"{height:.1f}",
            xy=(bar.get_x() + bar.get_width() / 2.0, height),
            xytext=(0, 2),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8,
        )

    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)


def render_bqi_stacked_chart(summary_df):
    """图 B：BI 得分值与种类数得分值堆积柱状图，并在 Y 轴标注 BQI 等级线。"""
    _configure_matplotlib()
    sites = summary_df["样点"].astype(str).tolist()
    bi_score = summary_df["BI 得分值"].astype(float).tolist()
    s_score = summary_df["物种数得分值"].astype(float).tolist()

    x = np.arange(len(sites))
    width = 0.5
    fig, ax = plt.subplots(figsize=(max(6.0, len(sites) * 1.3), 5.2))

    bars_bi = ax.bar(x, bi_score, width, label="BI 得分值", color="#4ba3e3")
    bars_s = ax.bar(x, s_score, width, bottom=bi_score, label="物种数得分值", color="#f2a93b")

    ax.set_xlabel("点位")
    ax.set_ylabel("堆积得分")
    ax.set_title("图 B：BI 得分与种类数得分堆积")
    ax.set_xticks(x)
    ax.set_xticklabels(sites)
    ax.set_ylim(0, 100)

    # BQI 评价等级线及右侧批注（0-100）
    grade_bands = [
        (0, 40, "非常不健康"),
        (40, 55, "不健康"),
        (55, 70, "亚健康"),
        (70, 85, "健康"),
        (85, 100, "非常健康"),
    ]
    for threshold in (40, 55, 70, 85):
        ax.axhline(threshold, color="#9ca3af", linestyle="--", linewidth=0.8, alpha=0.7)
    for lo, hi, label in grade_bands:
        mid = (lo + hi) / 2.0
        ax.text(1.02, mid / 100.0, label, transform=ax.transAxes,
                va="center", ha="left", fontsize=8, color="black")

    for bar in bars_bi:
        h = bar.get_height()
        if h > 0:
            ax.annotate(
                f"{h:.1f}",
                xy=(bar.get_x() + bar.get_width() / 2.0, h),
                xytext=(0, 2),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=8,
            )
    for bar, base in zip(bars_s, bi_score):
        total = bar.get_height() + base
        ax.annotate(
            f"{bar.get_height():.1f}",
            xy=(bar.get_x() + bar.get_width() / 2.0, total),
            xytext=(0, 2),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8,
        )

    ax.legend(loc="upper right")
    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)


st.title("BQI 底栖状况指数评价")

with st.expander("📐 BQI 计算公式", expanded=False):
    st.markdown("""
    **底栖动物状况指数按照如下公式进行计算：**

    $$\\text{BQI} = 50 \\times \\frac{10 - \\text{BI}}{10 - \\text{BI}_{\\text{ref}}} + 50 \\times \\frac{S}{S_{\\text{ref}}}$$

    | 参数 | 含义 | 春季 | 秋季 |
    |------|------|------|------|
    | BI | 底栖动物 BI 指数监测值 | — | — |
    | BI_ref | BI 指数期望值（按流域+海拔分区） | 6.09 | 5.44 |
    | S | 底栖动物物种数监测值（分类单元数） | — | — |
    | S_ref | 物种数期望值 | 20 | 17 |

    > 当 (10−BI)/(10−BI_ref) 和 S/S_ref 比值超过 1 时按 1 计。

    **BQI 得分评价等级：**

    | BQI 得分 | 底栖动物状况等级 |
    |---------|----------------|
    | 85 – 100 | 非常健康 |
    | 70 – 85 | 健康 |
    | 55 – 70 | 亚健康 |
    | 40 – 55 | 不健康 |
    | < 40 | 非常不健康 |
    """, unsafe_allow_html=False)

# ============================================================
# 多点位批量上传分析
# ============================================================
st.divider()
section_title("多点位数据上传分析")

col_season, col_fmt = st.columns([1, 2])
with col_season:
    season = st.selectbox("季节", ["spring", "autumn"], format_func=lambda x: "🌸 春季" if x == "spring" else "🍂 秋季", key="bqi_season")
with col_fmt:
    st.caption("上传 CSV 或 Excel 文件（长格式三列）：`样点`、`鉴定单元`、`物种数量`，每行一条记录，样点可重复出现。")

# CSV 模板下载
_TEMPLATE_CSV = (
    "样点,鉴定单元,物种数量\n"
    "湖心_01,杆丝蚓属,12\n"
    "湖心_01,蚌科,5\n"
    "湖心_01,锐缘龙虱属,3\n"
    "湖心_01,象甲科,4\n"
    "湖心_01,泥甲科,8\n"
    "入湖口_02,铁线虫纲,18\n"
    "入湖口_02,杆丝蚓属,25\n"
    "入湖口_02,霍甫水丝蚓,30\n"
    "入湖口_02,摇蚊科,15\n"
    "近岸区_03,石田螺,22\n"
    "近岸区_03,河篮蛤,15\n"
    "近岸区_03,纹沼螺,10\n"
    "近岸区_03,细蟌科,6\n"
    "生态区_04,石田螺,28\n"
    "生态区_04,河篮蛤,18\n"
    "生态区_04,泥甲科,10\n"
    "生态区_04,锐缘龙虱属,7\n"
    "生态区_04,蚌科,12\n"
)
st.download_button(
    "下载 CSV 模板",
    data=_TEMPLATE_CSV.encode("utf-8-sig"),
    file_name="bqi_template.csv",
    mime="text/csv",
    help="模版为长格式三列：样点、鉴定单元、物种数量。支持 CSV 和 Excel 格式。"
)

uploaded_file = st.file_uploader("上传数据文件", type=["csv", "xlsx"], key="bqi_file_upload")

if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()
    filename = uploaded_file.name
    is_excel = filename.lower().endswith(".xlsx") or filename.lower().endswith(".xls")
    mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if is_excel else "text/csv"

    with st.spinner(f"正在解析并计算 BQI（{season}）..."):
        result_batch = api.post_file(
            "/bqi/batch_calculate",
            file_bytes,
            filename=filename,
            mime=mime,
            extra_data={"season": season},
        )

    if not result_batch.get("success"):
        error_box(f"上传失败：{result_batch.get('error', '未知错误')}")
    else:
        data = result_batch["data"]
        samples = data["samples"]
        summary = data["summary"]
        unknown = data.get("unknown_species", [])

        st.session_state.last_bqi_batch = data

        # 总览卡片（断面数目 / 平均 BQI·平均 BI / 最优·最差站点）
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            metric_card("断面数目", str(summary["count"]), "已解析样本", color="#1d4ed8")
        with col_b:
            metric_card(
                "平均 BQI / 平均 BI",
                f"{summary['avg_bqi']:.2f}<span style='font-size:1rem;color:#6b7280;'> / BI {summary['avg_bi']:.2f}</span>",
                "全样本均值（越高越好）",
                color="#6366f1",
            )
        with col_c:
            metric_card(
                "最优 / 最差站点",
                f"{summary['best_site']} · {summary['worst_site']}",
                f"BQI {summary['max_bqi']:.2f} / {summary['min_bqi']:.2f}",
                color="#8b5cf6",
            )

        # ── 各点位 BQI 及分项得分（图 A + 图 B） ──
        section_title(f"各点位 BQI 及分项得分 — {data.get('season_label', season)}")
        summary_df = pd.DataFrame([{
            "样点": s["site_name"],
            "物种数 (S_obs)": s["species_count"],
            "BI 监测值": s["bi"],
            "BI 得分值": s["bi_score"],
            "物种数得分值": s["s_score"],
            "BQI 得分 (100分制)": s["bqi"],
            "底栖动物状况等级": s["grade_name"],
        } for s in samples])
        render_bqi_score_chart(summary_df)
        render_bqi_stacked_chart(summary_df)

        # ── 完整评估结果表（颜色高亮） ──
        section_title("底栖动物状况评估结果")
        grade_colors = {s["grade_name"]: s["grade_color"] for s in samples}

        def _style_grade(row):
            color = grade_colors.get(row["底栖动物状况等级"], "#ffffff")
            return [
                f"background-color: {color}40; font-weight: 600" if col == "底栖动物状况等级" else ""
                for col in row.index
            ]

        st.dataframe(
            summary_df.style.apply(_style_grade, axis=1),
            use_container_width=True,
            hide_index=True,
        )

        # ── 物种匹配明细表（含匹配方式） ──
        detail_rows = []
        for s in samples:
            for d in s.get("matched_details", []):
                detail_rows.append({
                    "样点": s["site_name"],
                    "鉴定单元": d.get("name", ""),
                    "数量": d.get("count", ""),
                    "耐污值": d.get("tolerance_value", ""),
                    "匹配方式": d.get("match_method", d.get("match_level", "")),
                })
        if detail_rows:
            with st.expander("🔬 物种匹配明细（含匹配方式）", expanded=False):
                st.dataframe(pd.DataFrame(detail_rows), use_container_width=True, hide_index=True)

        # ── 未匹配物种编辑区 ──
        if unknown:
            st.divider()
            section_title("未匹配物种编辑区")
            warning_box(
                f"⚠️ 检测到 {len(unknown)} 个物种未在国标数据库中匹配到耐污值（已按默认 Si=5.0 计算）。"
                f"您可以在下方手动指定耐污值后重新计算。"
            )
            with st.form("bqi_edit_tolerance"):
                edit_values = {}
                cols = st.columns(min(3, len(unknown)))
                for i, sp in enumerate(unknown):
                    with cols[i % 3]:
                        edit_values[sp] = st.number_input(
                            f"{sp}",
                            min_value=0.0, max_value=10.0, value=5.0, step=0.1,
                            key=f"bqi_edit_{sp}",
                        )
                if st.form_submit_button("应用自定义耐污值并重新计算", type="primary", use_container_width=True):
                    # 重新上传并传入自定义耐污值
                    st.info("自定义耐污值功能将在后续版本中通过 API 参数传递，当前版本请先调整 CSV 中的物种名使其匹配数据库。")
                    st.rerun()

        if st.button("发送批量结果到 AI 助手"):
            st.session_state.ai_context = {
                "batch_bqi_summary": summary,
                "samples_count": len(samples),
                "worst_site": summary["worst_site"],
                "best_site": summary["best_site"],
            }
            success_box("已附加批量 BQI 摘要到 AI 助手")


# ============================================================
# 完整耐污值数据库查询（1576 条国标）
# ============================================================
st.divider()
section_title("耐污值数据库查询")
st.caption("基于《中国淡水大型底栖无脊椎动物耐污值（试行）》（1576 条）。支持中文/拉丁名模糊搜索。")

with st.container():
    col_search, col_size = st.columns([3, 1])
    with col_search:
        search_query = st.text_input(
            "搜索关键字（留空查看全部）",
            value="",
            placeholder="如：颤蚓、Tubif、摇蚊、蜉蝣、涡虫...",
            key="bqi_db_search",
        )
    with col_size:
        page_size = st.selectbox("每页条数", [20, 50, 100, 200], index=1, key="bqi_db_pagesize")

    if "bqi_db_page" not in st.session_state:
        st.session_state.bqi_db_page = 1

    search_params = {"q": search_query, "page": st.session_state.bqi_db_page, "page_size": page_size}
    search_result = api.get("/bqi/species/search", params=search_params)

    if not search_result.get("success"):
        error_box(f"查询失败：{search_result.get('error', '未知错误')}")
    else:
        data = search_result["data"]
        meta = search_result["meta"]
        info_box(f"共 **{meta['total']}** 条匹配记录（第 {meta['page']}/{meta['pages']} 页）")

        if data:
            import pandas as pd
            df = pd.DataFrame([{
                "ID": r.get("id", ""),
                "门": r.get("phylum", ""),
                "纲": r.get("class_name", ""),
                "目": r.get("order_name", ""),
                "科": r.get("family", ""),
                "属": r.get("genus", ""),
                "耐污值": r.get("tolerance_value", ""),
            } for r in data])
            st.dataframe(df, use_container_width=True, hide_index=True)

        col_prev, col_next, col_jump = st.columns([1, 1, 2])
        with col_prev:
            if st.button("◀ 上一页", disabled=(meta["page"] <= 1), use_container_width=True):
                st.session_state.bqi_db_page -= 1
                st.rerun()
        with col_next:
            if st.button("下一页 ▶", disabled=(meta["page"] >= meta["pages"]), use_container_width=True):
                st.session_state.bqi_db_page += 1
                st.rerun()
        with col_jump:
            jump_to = st.number_input(
                "跳转到页", min_value=1, max_value=max(1, meta["pages"]),
                value=meta["page"], step=1, key="bqi_db_jump"
            )
            if st.button("跳转", use_container_width=True):
                st.session_state.bqi_db_page = int(jump_to)
                st.rerun()

# 单物种精确查询
with st.expander("🔍 单物种精确查询耐污值"):
    single_name = st.text_input(
        "输入物种名（中文属名/拉丁属名/科名均可）",
        value="",
        placeholder="如：颤蚓属 / Tubifex / 摇蚊科",
        key="bqi_single_lookup",
    )
    if single_name:
        lookup = api.get("/bqi/species/lookup", params={"name": single_name})
        if lookup.get("success"):
            ld = lookup["data"]
            if ld.get("found"):
                level_label = {
                    "genus": "属级精确匹配",
                    "family": "科级精确匹配",
                    "order": "目级精确匹配",
                    "class": "纲级精确匹配",
                    "phylum": "门级精确匹配",
                    "fuzzy": "模糊匹配",
                }.get(ld["match_level"], ld["match_level"])
                success_box(
                    f"✅ 匹配成功：**{ld['name']}** → 耐污值 **{ld['tolerance_value']:.2f}**（{level_label}）"
                )
            else:
                warning_box(f"⚠️ 未在国标数据库中找到「{ld['name']}」，建议核对物种名或使用模糊搜索查看相近条目")
        else:
            error_box(lookup.get("error", "查询失败"))