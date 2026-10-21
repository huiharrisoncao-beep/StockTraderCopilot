"""Demo screening rules. These thresholds are explainable, not a validated strategy."""

from __future__ import annotations

RULE_SET = "trend_volume_v1"

RULES = {
    "name": RULE_SET,
    "min_history": 60,
    "min_return_20d": 0.05,
    "max_return_20d": 0.40,
    "min_volume_ratio": 1.2,
    "max_volume_ratio": 3.0,
    "candidate_limit": 10,
    "note": "演示用可解释规则，不是经过验证的交易策略，也不构成投资建议。",
}
