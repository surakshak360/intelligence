"""
Deterministic fusion logic.

The weighted formula below is taken verbatim from GROUND_RULES.md
section 10.2 ("Fusion Logic (Deterministic)") — do not swap this for a
learned model; section 10.1 explicitly rules that out for this service.
"""
from typing import Literal

WEIGHTS = {
    "scam_risk": 0.5,
    "vision_risk": 0.3,
    "user_priority": 0.2,
}

PRIORITY_SCORE = {"low": 0.2, "medium": 0.5, "high": 0.8, "critical": 1.0}

# Score -> risk_level bucket boundaries. Documented choice (not in
# GROUND_RULES verbatim): critical needs BOTH a high score and it being
# consistent with how section 5.1's `cases.priority` enum reads
# (low/medium/high/critical), so we mirror that same 4-way split here.
RISK_LEVEL_THRESHOLDS: list[tuple[float, str]] = [
    (0.85, "critical"),
    (0.6, "high"),
    (0.35, "medium"),
]


def fuse_risk(scam_result: dict | None, vision_result: dict | None, user_report: dict | None) -> float:
    scam_result = scam_result or {}
    vision_result = vision_result or {}
    user_report = user_report or {}

    scam_score = scam_result.get("risk_score", 0) or 0
    vision_score = vision_result.get("risk_score", 0) if vision_result else 0
    user_score = PRIORITY_SCORE.get(user_report.get("priority", "medium"), 0.5)

    return (
        WEIGHTS["scam_risk"] * scam_score
        + WEIGHTS["vision_risk"] * vision_score
        + WEIGHTS["user_priority"] * user_score
    )


def risk_level_for(score: float) -> Literal["low", "medium", "high", "critical"]:
    for threshold, level in RISK_LEVEL_THRESHOLDS:
        if score >= threshold:
            return level  # type: ignore[return-value]
    return "low"
