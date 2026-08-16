"""Drinking water source thresholds and policy references."""

from __future__ import annotations

from typing import Dict, List

DRINKING_WATER_LIMITS = {
    "chla": 10.0,
    "tp": 0.05,
    "tn": 1.0,
    "sd": 1.5,
    "cod_mn": 4.0,
}

POLICY_REFERENCES = [
    {
        "title": "统筹流域治理",
        "content": "坚持「预防为主、防治结合」，将湖库及其汇水区域作为整体，协调工业、城镇、农业农村等多污染源管控。",
    },
    {
        "title": "控制外源负荷",
        "content": "优先削减氮、磷等营养盐输入，重视生活污水收集处理、农业面源与畜禽养殖污染防治。",
    },
    {
        "title": "重视饮用水安全",
        "content": "对饮用水源保护区及周边强化风险防控，防范突发性污染事故。",
    },
    {
        "title": "内源与生态修复",
        "content": "在条件适宜区域，可结合底泥治理、水生植被恢复、鱼类群落调控等措施改善水体功能。",
    },
]

PRACTICAL_ADVICE = [
    "分级管控：综合 TLI 处于中营养附近时，以外源截污与负荷削减为主；进入富营养区间时，宜制定阶段性目标并加密监测。",
    "协同削减：若雷达图显示多项指标「压力」集中，优先推动 TN、TP、COD 同步管控与透明度改善。",
    "水源地与敏感水体：饮用水源地除关注营养盐外，应同步防范藻类衍生风险与有机物负荷。",
    "监测与复核：治理措施实施后，应以同一套指标与单位跟踪复测，避免单次采样误判。",
]


def check_drinking_water_warning(values: Dict[str, float], is_drinking_source: bool) -> dict:
    if not is_drinking_source:
        return {"warnings": [], "overall_level": "none"}

    warnings = []
    for key, limit in DRINKING_WATER_LIMITS.items():
        val = values.get(key, 0)
        if key == "sd":
            if val < limit:
                warnings.append({
                    "indicator": key,
                    "value": val,
                    "limit": limit,
                    "level": "warning",
                    "message": f"SD={val:.2f}m 低于饮用水源标准 {limit}m",
                })
        else:
            if val > limit:
                warnings.append({
                    "indicator": key,
                    "value": val,
                    "limit": limit,
                    "level": "warning",
                    "message": f"{key.upper()}={val:.4g} 超过饮用水源标准 {limit}",
                })

    from .tli_model import evaluate_tli
    total_tli = evaluate_tli(values)["total_tli"]
    if total_tli > 50:
        warnings.append({
            "indicator": "total_tli",
            "value": total_tli,
            "limit": 50,
            "level": "danger",
            "message": f"综合TLI={total_tli:.2f} 超过中营养阈值50，建议优先削减外源负荷",
        })

    overall_level = "danger" if any(w["level"] == "danger" for w in warnings) else \
                    "warning" if warnings else "ok"

    return {"warnings": warnings, "overall_level": overall_level}
