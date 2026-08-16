"""Collaborative reduction algorithms for eutrophication management.

设计理念（基于 OECD 标准 + Forsberg 比值判据 + 滇池 AEM3D 模拟研究）：
1. **绝对浓度优先**：TN/TP 超过过饱和阈值时，营养盐饱和，N:P 比无意义，按"光照/综合限制"处理
2. **低浓度区精细诊断**：TN/TP 低于阈值时，按 N:P 质量比判断限制因子（<7 氮限制、>14 磷限制、7~14 协同）
3. **差异化削减**：根据限制因子分配 TN/TP 削减权重（参考滇池研究：TP 25%见效、TN 50%才合理）
4. **Chl-a 响应函数**：Chl-a 不再是独立控制量，而是 TN/TP 削减后的响应结果（OECD 对数线性模型）
"""

from __future__ import annotations

import math
from typing import Dict, Tuple

from .tli_model import FIXED_WEIGHTS, concentration_from_tli, evaluate_tli, tli_single


# ====== 工程实务边界 ======
PRACTICAL_MIN = {
    "chla": 2.0,
    "tp": 0.005,
    "tn": 0.2,
    "cod_mn": 0.5,
}
PRACTICAL_MAX = {"sd": 10.0}


# ====== 营养盐饱和阈值（OECD 标准 + 经典文献） ======
# 当 TP > 0.1 mg/L 或 TN > 1.5 mg/L 时，水体营养盐过饱和
# 藻类生长主要受光照、温度等综合环境因素制约，N:P 比值失去生态学意义
TP_SATURATION_THRESHOLD = 0.1   # mg/L，过饱和下限（OECD 取 0.05~0.1，这里取上限）
TN_SATURATION_THRESHOLD = 1.5   # mg/L，过饱和下限（OECD 取 1.0~1.5，这里取上限）

# 低浓度区的 N:P 质量比阈值（Forsberg 标准，对应原子比 10 和 20）
NP_RATIO_N_LIMIT = 7.0     # 质量比 < 7（原子比 < 10）→ 氮限制
NP_RATIO_P_LIMIT = 14.0    # 质量比 > 14（原子比 > 20）→ 磷限制
# 7 ≤ N:P ≤ 14 → 氮磷协同限制


# ====== 差异化削减权重（基于限制因子） ======
# 参考滇池 AEM3D 研究：TP 削减 25% 即见效，TN 需 50% 才合理
# 权重表示相对于统一削减率 r 的放大/缩小倍数
CUT_WEIGHTS = {
    "saturated":   {"tn": 1.0, "tp": 1.0, "cod_mn": 1.0},  # 过饱和：综合削减
    "n_limited":   {"tn": 1.5, "tp": 0.7, "cod_mn": 1.0},  # 氮限制：TN 重点削减
    "p_limited":   {"tn": 0.7, "tp": 1.5, "cod_mn": 1.0},  # 磷限制：TP 重点削减
    "co_limited":  {"tn": 1.0, "tp": 1.0, "cod_mn": 1.0},  # 协同：同步削减
}


# ====== Chl-a 响应函数（OECD 对数线性模型） ======
# log10(Chl-a) = a + b_TP·log10(TP) + b_TN·log10(TN)
# 系数来源：OECD Eutrophication of Waters (1982) 综合监测报告
CHLA_RESP_COEFFS = {
    "intercept": -0.432,
    "tp_elasticity": 0.79,    # TP 弹性系数
    "tn_elasticity": 0.40,    # TN 弹性系数
}


def diagnose_nutrient_limitation(values: dict) -> dict:
    """两步分级诊断营养盐限制因子。

    第一步：绝对浓度阈值过滤
        - TP > 0.1 mg/L 或 TN > 1.5 mg/L → 营养盐过饱和，光照/综合限制
    第二步：低浓度区精细诊断（N:P 质量比）
        - N:P < 7（原子比 < 10）→ 氮限制
        - N:P > 14（原子比 > 20）→ 磷限制
        - 7 ≤ N:P ≤ 14 → 氮磷协同限制
    """
    tn = float(values.get("tn", 0))
    tp = float(values.get("tp", 0))

    # 防止除零
    np_ratio = tn / tp if tp > 1e-9 else float("inf")

    # 第一步：绝对浓度阈值
    if tp > TP_SATURATION_THRESHOLD or tn > TN_SATURATION_THRESHOLD:
        exceeded = []
        if tp > TP_SATURATION_THRESHOLD:
            exceeded.append(f"TP={tp:.3f} mg/L > {TP_SATURATION_THRESHOLD}")
        if tn > TN_SATURATION_THRESHOLD:
            exceeded.append(f"TN={tn:.3f} mg/L > {TN_SATURATION_THRESHOLD}")
        return {
            "type": "saturated",
            "label": "营养盐过饱和（光照/综合限制）",
            "description": (
                f"当前 {', '.join(exceeded)}，水体营养盐处于饱和/过剩状态。"
                "藻类生长主要受光照、温度、水动力等综合环境因素制约，"
                "N:P 比值参考意义有限。建议采取综合削减措施（外源控制 + 生态修复）。"
            ),
            "primary_factor": "light_temp",
            "use_ratio": False,
            "np_ratio": round(np_ratio, 2) if np_ratio != float("inf") else None,
            "tn": tn,
            "tp": tp,
            "thresholds": {
                "tp_saturation": TP_SATURATION_THRESHOLD,
                "tn_saturation": TN_SATURATION_THRESHOLD,
                "np_n_limit": NP_RATIO_N_LIMIT,
                "np_p_limit": NP_RATIO_P_LIMIT,
            },
        }

    # 第二步：N:P 比值判断
    if np_ratio == float("inf"):
        return {
            "type": "p_limited",
            "label": "磷限制（TP 极低）",
            "description": f"TP={tp:.4f} mg/L 极低，TN={tn:.3f} mg/L，TP 为绝对限制因子",
            "primary_factor": "tp",
            "use_ratio": True,
            "np_ratio": None,
            "tn": tn,
            "tp": tp,
            "thresholds": {
                "tp_saturation": TP_SATURATION_THRESHOLD,
                "tn_saturation": TN_SATURATION_THRESHOLD,
                "np_n_limit": NP_RATIO_N_LIMIT,
                "np_p_limit": NP_RATIO_P_LIMIT,
            },
        }

    if np_ratio < NP_RATIO_N_LIMIT:
        return {
            "type": "n_limited",
            "label": "氮限制",
            "description": (
                f"N:P 质量比 = {np_ratio:.2f}（< {NP_RATIO_N_LIMIT}，对应原子比 < 10），"
                f"TN 为首要控制因子。建议重点削减氮源（如尾水脱氮、面源控制）。"
            ),
            "primary_factor": "tn",
            "use_ratio": True,
            "np_ratio": round(np_ratio, 2),
            "tn": tn,
            "tp": tp,
            "thresholds": {
                "tp_saturation": TP_SATURATION_THRESHOLD,
                "tn_saturation": TN_SATURATION_THRESHOLD,
                "np_n_limit": NP_RATIO_N_LIMIT,
                "np_p_limit": NP_RATIO_P_LIMIT,
            },
        }

    if np_ratio > NP_RATIO_P_LIMIT:
        return {
            "type": "p_limited",
            "label": "磷限制",
            "description": (
                f"N:P 质量比 = {np_ratio:.2f}（> {NP_RATIO_P_LIMIT}，对应原子比 > 20），"
                f"TP 为首要控制因子。建议重点削减磷源（如禁磷、污水除磷、底泥疏浚）。"
            ),
            "primary_factor": "tp",
            "use_ratio": True,
            "np_ratio": round(np_ratio, 2),
            "tn": tn,
            "tp": tp,
            "thresholds": {
                "tp_saturation": TP_SATURATION_THRESHOLD,
                "tn_saturation": TN_SATURATION_THRESHOLD,
                "np_n_limit": NP_RATIO_N_LIMIT,
                "np_p_limit": NP_RATIO_P_LIMIT,
            },
        }

    # 协同限制
    return {
        "type": "co_limited",
        "label": "氮磷协同限制",
        "description": (
            f"N:P 质量比 = {np_ratio:.2f}（{NP_RATIO_N_LIMIT}~{NP_RATIO_P_LIMIT}，"
            f"对应原子比 10~20），TN、TP 协同控制。"
            f"建议同步削减氮磷（参考滇池研究：TN+TP 同时削减 10% 或 50% 以上"
            f"效果显著优于单一营养盐削减）。"
        ),
        "primary_factor": "both",
        "use_ratio": True,
        "np_ratio": round(np_ratio, 2),
        "tn": tn,
        "tp": tp,
        "thresholds": {
            "tp_saturation": TP_SATURATION_THRESHOLD,
            "tn_saturation": TN_SATURATION_THRESHOLD,
            "np_n_limit": NP_RATIO_N_LIMIT,
            "np_p_limit": NP_RATIO_P_LIMIT,
        },
    }


def predict_chla_response(base_values: dict, new_values: dict) -> float:
    """基于 OECD 对数线性响应模型，预测 TN/TP 变化后的 Chl-a。

    采用相对弹性法（不依赖绝对预测，只看变化响应）：
        Chl-a_new / Chl-a_base = (TP_new/TP_base)^b_TP × (TN_new/TN_base)^b_TN

    这样避免了绝对预测的系数偏差，只反映 TN/TP 削减对 Chl-a 的相对影响。

    系数：b_TP=0.79, b_TN=0.40（OECD 1982 综合监测报告）
    """
    base_chla = max(float(base_values.get("chla", 1.0)), 0.1)
    base_tp = max(float(base_values.get("tp", 0.01)), 1e-4)
    base_tn = max(float(base_values.get("tn", 0.1)), 1e-3)

    new_tp = max(float(new_values.get("tp", base_tp)), 1e-4)
    new_tn = max(float(new_values.get("tn", base_tn)), 1e-3)

    tp_ratio = new_tp / base_tp
    tn_ratio = new_tn / base_tn

    # Chl-a 相对变化
    chla_ratio = (tp_ratio ** CHLA_RESP_COEFFS["tp_elasticity"]) * \
                 (tn_ratio ** CHLA_RESP_COEFFS["tn_elasticity"])

    new_chla = base_chla * chla_ratio
    return max(new_chla, PRACTICAL_MIN["chla"])


def apply_collaborative_reduction(
    base_values: dict,
    reduction_ratio: float,
    chla_mode: str = "auto",   # 保留参数兼容旧调用，默认 auto 走新算法
    chla_link_coeff: float = 0.6,  # 保留参数兼容
    target_total_tli: float = 50.0,
    limitation: dict = None,   # 可传入预计算的限制诊断结果
) -> dict:
    """根据限制因子差异化削减各指标，Chl-a 由响应函数自动推算。"""
    ratio = max(0.0, min(float(reduction_ratio), 1.0))

    # 若未传入限制诊断，先诊断
    if limitation is None:
        limitation = diagnose_nutrient_limitation(base_values)

    weights = CUT_WEIGHTS.get(limitation["type"], CUT_WEIGHTS["co_limited"])

    out = dict(base_values)
    # TN/TP/CODMn 按差异化权重削减
    for k in ["tn", "tp", "cod_mn"]:
        eff_ratio = min(1.0, ratio * weights[k])
        out[k] = max(PRACTICAL_MIN[k], base_values[k] * (1 - eff_ratio))

    # SD 按统一比例提升（受 Chl-a 反馈影响）
    out["sd"] = min(PRACTICAL_MAX["sd"], base_values["sd"] * (1 + ratio))

    # Chl-a 由响应函数计算（取代旧的 A/B/C 模式）
    out["chla"] = predict_chla_response(base_values, out)

    return out


def solve_uniform_reduction_to_target(
    base_values: dict,
    target_total_tli: float = 50.0,
    chla_mode: str = "auto",
    chla_link_coeff: float = 0.6,
    limitation: dict = None,
) -> dict:
    """二分法求解达到目标 TLI 所需的统一削减率 r（差异化作用于各指标）。"""
    if limitation is None:
        limitation = diagnose_nutrient_limitation(base_values)

    lo, hi = 0.0, 1.0
    best_values = dict(base_values)
    best_tli = evaluate_tli(base_values)["total_tli"]

    for _ in range(60):
        mid = (lo + hi) / 2
        candidate = apply_collaborative_reduction(
            base_values,
            mid,
            chla_mode=chla_mode,
            chla_link_coeff=chla_link_coeff,
            target_total_tli=target_total_tli,
            limitation=limitation,
        )
        candidate_tli = evaluate_tli(candidate)["total_tli"]
        best_values = candidate
        best_tli = candidate_tli
        if candidate_tli <= target_total_tli:
            hi = mid
        else:
            lo = mid

    final_ratio = hi
    final_values = apply_collaborative_reduction(
        base_values,
        final_ratio,
        chla_mode=chla_mode,
        chla_link_coeff=chla_link_coeff,
        target_total_tli=target_total_tli,
        limitation=limitation,
    )
    final_tli = evaluate_tli(final_values)["total_tli"]

    at_constraints = {
        "tn": final_values["tn"] <= PRACTICAL_MIN["tn"] + 1e-12,
        "tp": final_values["tp"] <= PRACTICAL_MIN["tp"] + 1e-12,
        "cod_mn": final_values["cod_mn"] <= PRACTICAL_MIN["cod_mn"] + 1e-12,
        "sd": final_values["sd"] >= PRACTICAL_MAX["sd"] - 1e-12,
    }
    reachable = final_tli <= target_total_tli + 1e-3

    return {
        "ratio": final_ratio,
        "values": final_values,
        "tli": final_tli,
        "reachable": reachable,
        "constraints_hit": at_constraints,
        "limitation": limitation,
    }


def build_smart_scheme(
    base_values: dict,
    target_tli: float,
    chla_mode: str = "auto",
    chla_link_coeff: float = 0.6,
) -> dict:
    """生成智能削减方案，包含限制因子诊断 + 差异化削减策略 + Chl-a 响应。"""
    # 先做限制因子诊断
    limitation = diagnose_nutrient_limitation(base_values)

    plan = solve_uniform_reduction_to_target(
        base_values,
        target_total_tli=target_tli,
        chla_mode=chla_mode,
        chla_link_coeff=chla_link_coeff,
        limitation=limitation,
    )
    plan_values = plan["values"]

    # 计算各指标实际削减比例（已含差异化权重）
    tn_cut = (1 - plan_values["tn"] / max(base_values["tn"], 1e-9)) * 100
    tp_cut = (1 - plan_values["tp"] / max(base_values["tp"], 1e-9)) * 100
    cod_cut = (1 - plan_values["cod_mn"] / max(base_values["cod_mn"], 1e-9)) * 100
    sd_up = (plan_values["sd"] / max(base_values["sd"], 1e-9) - 1) * 100
    chla_change = (plan_values["chla"] / max(base_values["chla"], 1e-9) - 1) * 100

    # 根据限制因子生成针对性建议
    if limitation["type"] == "saturated":
        strategy = (
            "由于营养盐过饱和，单纯削减 TN/TP 难以快速降低 Chl-a。"
            "建议综合措施：① 强化外源控制（污水厂提标、面源拦截）；"
            "② 叠加生态修复（沉水植物恢复、生态浮岛、鱼类调控）以提升 SD、抑制藻类；"
            "③ 必要时采取应急措施（藻水分离、絮凝沉降）。"
        )
    elif limitation["type"] == "n_limited":
        strategy = (
            "氮限制水体，应优先削减氮源：① 污水厂升级脱氮工艺；"
            "② 控制农业面源氮流失（精准施肥、缓冲带）；"
            "③ 内源氮释放控制（底泥疏浚、曝气氧化）。"
            f"在当前方案下 TN 削减 {tn_cut:.1f}%，TP 削减 {tp_cut:.1f}%。"
        )
    elif limitation["type"] == "p_limited":
        strategy = (
            "磷限制水体，应优先削减磷源：① 禁磷/限磷政策；"
            "② 污水厂化学除磷或生物除磷；"
            "③ 内源磷控制（底泥疏浚、磷钝化剂投放）。"
            f"在当前方案下 TP 削减 {tp_cut:.1f}%，TN 削减 {tn_cut:.1f}%。"
        )
    else:  # co_limited
        strategy = (
            "氮磷协同限制，应同步削减：① TN+TP 同时削减效果显著优于单一削减"
            "（参考滇池 AEM3D 研究）；② 比例参考 N:P 比维持生态平衡。"
            f"在当前方案下 TN 削减 {tn_cut:.1f}%，TP 削减 {tp_cut:.1f}%。"
        )

    summary = (
        f"统一削减率约 {plan['ratio']*100:.1f}%"
        f"（{limitation['label']}），"
        f"预计综合 TLI 可降至 {plan['tli']:.2f}。"
    )
    detail = (
        f"差异化削减：TN {tn_cut:.1f}%、TP {tp_cut:.1f}%、CODMn {cod_cut:.1f}%，"
        f"SD 提升 {sd_up:.1f}%。"
        f"Chl-a 由响应函数推算变化 {chla_change:+.1f}%"
        f"（OECD 模型：log10(Chl-a) ∝ 0.79·log10(TP) + 0.40·log10(TN)）。"
        f"削减后 TN 约 {plan_values['tn']:.3f} mg/L、"
        f"TP 约 {plan_values['tp']:.4f} mg/L、"
        f"CODMn 约 {plan_values['cod_mn']:.3f} mg/L、"
        f"Chl-a 约 {plan_values['chla']:.2f} μg/L、"
        f"SD 约 {plan_values['sd']:.2f} m。"
    )

    return {
        "ratio": plan["ratio"],
        "values": plan_values,
        "tli": plan["tli"],
        "reachable": plan["reachable"],
        "constraints_hit": plan["constraints_hit"],
        "limitation": limitation,
        "strategy": strategy,
        "cuts": {
            "tn": round(tn_cut, 1),
            "tp": round(tp_cut, 1),
            "cod_mn": round(cod_cut, 1),
            "sd": round(sd_up, 1),
            "chla": round(chla_change, 1),
        },
        "summary": summary,
        "detail": detail,
    }


def function_curve(indicator: str, anchor_value: float = None) -> dict:
    ranges = {
        "chla": (0.1, 200.0),
        "tp": (0.001, 2.0),
        "tn": (0.01, 10.0),
        "sd": (0.05, 10.0),
        "cod_mn": (0.1, 20.0),
    }
    xmin, xmax = ranges[indicator]
    import numpy as np
    x_curve = np.linspace(xmin, xmax, 300).tolist()
    y_curve = [tli_single(indicator, x) for x in x_curve]
    anchor = None
    if anchor_value is not None:
        anchor = {"x": anchor_value, "y": tli_single(indicator, anchor_value)}
    return {
        "indicator": indicator,
        "x": x_curve,
        "y": y_curve,
        "anchor": anchor,
        "ref_lines": [50, 60, 70],
    }
