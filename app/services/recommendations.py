"""
Recommendation rule engine — the `recommendations` block of /fuse
(GROUND_RULES 6.3 example):

    "recommendations": {
      "citizen": ["Block number", "Report to 1930", "Monitor bank accounts"],
      "officer": ["Freeze linked accounts", "Request CDR for +91...", ...],
      "analyst": ["Add to digital arrest campaign tracking", ...]
    }

Pure rule-based (no LLM call here) so the service stays CPU-only per
GROUND_RULES 9.4 / 10.1. surakshak360-scam-intelligence already produces
free-text recommendations via its LLM step (section 6.1) — this engine
adds the *investigation-specific* recommendations that depend on graph
context (linked cases, network pattern) which only this service has.
"""

CITIZEN_BASE = ["Do not share OTPs, PINs, or passwords with anyone.", "Report to the 1930 cybercrime helpline."]

SCAM_TYPE_CITIZEN_ADVICE = {
    "digital_arrest": ["Do not transfer money.", "Block the number.", "Government agencies never arrest over video call."],
    "phishing": ["Do not click the link.", "Change passwords for any account you entered on that page."],
    "counterfeit": ["Do not attempt to circulate the note.", "Surrender it to the nearest bank or police station."],
}


def build_recommendations(
    risk_level: str,
    scam_type: str | None,
    pattern: str,
    linked_case_count: int,
    central_entities: list[str],
) -> dict:
    citizen = list(CITIZEN_BASE)
    if scam_type in SCAM_TYPE_CITIZEN_ADVICE:
        citizen = SCAM_TYPE_CITIZEN_ADVICE[scam_type] + citizen
    if risk_level in ("high", "critical"):
        citizen.append("Monitor linked bank accounts closely for the next 30 days.")

    officer: list[str] = []
    if risk_level in ("high", "critical"):
        officer.append("Prioritize for immediate triage.")
    for entity in central_entities[:3]:
        officer.append(f"Request call detail records / KYC trace for {entity}.")
    if linked_case_count > 0:
        officer.append(f"Cross-reference with {linked_case_count} linked case(s) before closing.")
    if pattern == "mule_network":
        officer.append("Flag linked accounts to banking partner for freeze review.")
    if not officer:
        officer.append("Standard intake — no elevated action required yet.")

    analyst: list[str] = []
    if pattern != "isolated_report":
        analyst.append(f"Add to '{pattern}' campaign tracking.")
    if linked_case_count >= 3:
        analyst.append("Escalate cluster for cross-jurisdiction coordination review.")
    if not analyst:
        analyst.append("No campaign-level action — insufficient linked evidence yet.")

    return {"citizen": citizen, "officer": officer, "analyst": analyst}
