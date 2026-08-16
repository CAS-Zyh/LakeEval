"""TLI computation utilities for eutrophication assessment."""

from __future__ import annotations

from typing import Dict, Tuple

import math

FIXED_WEIGHTS: Dict[str, float] = {
    "chla": 0.2662,
    "tn": 0.1790,
    "tp": 0.1878,
    "sd": 0.1834,
    "cod_mn": 0.1834,
}

INDICATOR_LABELS: Dict[str, str] = {
    "chla": "Chl-a (μg/L)",
    "tp": "TP (mg/L)",
    "tn": "TN (mg/L)",
    "sd": "SD (m)",
    "cod_mn": "CODMn (mg/L)",
}

EPS = 1e-9


def safe_positive(value: float) -> float:
    return max(float(value), EPS)


def tli_single(indicator: str, value: float) -> float:
    x = safe_positive(value)
    if indicator == "chla":
        return 10 * (2.5 + 1.086 * math.log(x))
    if indicator == "tp":
        return 10 * (9.436 + 1.624 * math.log(x))
    if indicator == "tn":
        return 10 * (5.453 + 1.694 * math.log(x))
    if indicator == "sd":
        return 10 * (5.118 - 1.94 * math.log(x))
    if indicator == "cod_mn":
        return 10 * (0.109 + 2.661 * math.log(x))
    raise KeyError(f"Unknown indicator: {indicator}")


def concentration_from_tli(indicator: str, target_tli: float) -> float:
    t = float(target_tli)
    if indicator == "chla":
        return math.exp((t / 10 - 2.5) / 1.086)
    if indicator == "tp":
        return math.exp((t / 10 - 9.436) / 1.624)
    if indicator == "tn":
        return math.exp((t / 10 - 5.453) / 1.694)
    if indicator == "sd":
        return math.exp((5.118 - t / 10) / 1.94)
    if indicator == "cod_mn":
        return math.exp((t / 10 - 0.109) / 2.661)
    raise KeyError(f"Unknown indicator: {indicator}")


def evaluate_tli(values: Dict[str, float]) -> Dict[str, object]:
    single_tli = {k: tli_single(k, values[k]) for k in FIXED_WEIGHTS}
    contributions = {k: FIXED_WEIGHTS[k] * single_tli[k] for k in FIXED_WEIGHTS}
    total_tli = sum(contributions.values())

    contribution_rate = {}
    if total_tli > 0:
        contribution_rate = {k: contributions[k] / total_tli for k in FIXED_WEIGHTS}

    return {
        "weights": FIXED_WEIGHTS,
        "single_tli": single_tli,
        "contributions": contributions,
        "contribution_rate": contribution_rate,
        "total_tli": total_tli,
    }


def tli_grade(total_tli: float) -> Tuple[str, str]:
    if total_tli < 30:
        return "贫营养", "#2ecc71"
    if total_tli < 50:
        return "中营养", "#f1c40f"
    if total_tli < 60:
        return "轻度富营养", "#f39c12"
    if total_tli < 70:
        return "中度富营养", "#e67e22"
    return "重度富营养", "#e74c3c"


def back_calculate_target(
    values: Dict[str, float],
    target_total_tli: float,
    main_pollutant: str,
) -> Dict[str, float]:
    eval_result = evaluate_tli(values)
    weights = eval_result["weights"]
    contributions = eval_result["contributions"]

    if main_pollutant not in weights:
        raise ValueError("Main pollutant key is invalid.")

    others_sum = sum(v for k, v in contributions.items() if k != main_pollutant)
    wj = weights[main_pollutant]
    if wj <= 0:
        raise ValueError("Invalid weight for main pollutant.")

    target_single_tli = (target_total_tli - others_sum) / wj
    target_concentration = concentration_from_tli(main_pollutant, target_single_tli)
    return {
        "target_single_tli": target_single_tli,
        "target_concentration": target_concentration,
    }
