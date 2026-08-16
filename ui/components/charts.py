import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from core.tli_model import tli_single, INDICATOR_LABELS

INDICATOR_COLORS = {
    "chla": "#1d4ed8",
    "tp": "#f59e0b",
    "tn": "#10b981",
    "sd": "#6366f1",
    "cod_mn": "#8b5cf6",
}

PLOT_RANGES = {
    "chla": (0.1, 200.0),
    "tp": (0.001, 2.0),
    "tn": (0.01, 10.0),
    "sd": (0.05, 10.0),
    "cod_mn": (0.1, 20.0),
}

POSITIONS = {"chla": (1, 1), "tp": (1, 2), "tn": (2, 1), "sd": (2, 2), "cod_mn": (3, 1)}


def render_function_curves(values: dict):
    fig = make_subplots(
        rows=3, cols=2,
        subplot_titles=[f"TLI({k})" for k in ["chla", "tp", "tn", "sd", "cod_mn"]],
        vertical_spacing=0.12,
    )

    for key, (xmin, xmax) in PLOT_RANGES.items():
        row, col = POSITIONS[key]
        x_curve = np.linspace(xmin, xmax, 300)
        y_curve = np.array([tli_single(key, x) for x in x_curve])
        fig.add_trace(
            go.Scatter(x=x_curve, y=y_curve, mode="lines", name=f"TLI({key})",
                       showlegend=False, line=dict(color=INDICATOR_COLORS[key], width=2)),
            row=row, col=col,
        )
        fig.add_trace(
            go.Scatter(
                x=[values[key]], y=[tli_single(key, values[key])],
                mode="markers+text", text=["锚点"], textposition="top center",
                marker=dict(size=10, color="#dc2626"), showlegend=False,
            ),
            row=row, col=col,
        )
        for ref in [50, 60, 70]:
            fig.add_hline(y=ref, line_dash="dash", line_color="#d1d5db", row=row, col=col)
        fig.update_xaxes(title_text=INDICATOR_LABELS[key], row=row, col=col)
        fig.update_yaxes(title_text="TLI", row=row, col=col)

    fig.update_layout(height=850, template="plotly_white")
    return fig


def render_radar_chart(current_profile: list, simulated_profile: list):
    categories = ["CHLA", "TP", "TN", "SD", "CODMN"]
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=current_profile + [current_profile[0]],
        theta=categories + [categories[0]],
        fill="toself", name="当前状态", opacity=0.45,
        line=dict(color="#dc2626"),
    ))
    fig.add_trace(go.Scatterpolar(
        r=simulated_profile + [simulated_profile[0]],
        theta=categories + [categories[0]],
        fill="toself", name="治理后状态", opacity=0.45,
        line=dict(color="#16a34a"),
    ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        template="plotly_white", height=420,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    )
    return fig


def render_contribution_bars(contribution_rate: dict):
    sorted_items = sorted(contribution_rate.items(), key=lambda x: x[1], reverse=True)
    fig = go.Figure()
    for key, rate in sorted_items:
        fig.add_trace(go.Bar(
            x=[key.upper()], y=[rate * 100],
            marker_color=INDICATOR_COLORS.get(key, "#6b7280"),
            text=[f"{rate*100:.1f}%"], textposition="outside",
            showlegend=False,
        ))
    fig.update_layout(
        yaxis_title="贡献率 (%)", template="plotly_white", height=300,
        margin=dict(l=40, r=20, t=20, b=40),
    )
    return fig
