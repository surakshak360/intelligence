SCAM_RESULT = {
    "transcript": "Hello, this is CBI officer calling about a parcel...",
    "language": "hi",
    "risk_score": 0.94,
    "scam_type": "digital_arrest",
    "confidence": 0.91,
    "entities": [
        {"type": "organization", "value": "CBI", "spoofed": True},
        {"type": "amount", "value": "50000", "currency": "INR"},
        {"type": "phone", "value": "+919876543210", "verified": False},
    ],
}

USER_REPORT = {
    "reporter_id": "user_1",
    "priority": "high",
    "case_type": "digital_arrest",
    "location": {"lat": 19.0760, "lng": 72.8777, "district": "Mumbai", "state": "Maharashtra"},
}


def test_fuse_basic(client):
    resp = client.post("/fuse", json={
        "case_id": "case_1",
        "scam_result": SCAM_RESULT,
        "user_report": USER_REPORT,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    result = body["result"]
    assert result["case_id"] == "case_1"
    assert result["risk_level"] in ("high", "critical")
    assert 0 <= result["overall_score"] <= 1
    assert result["evidence_package"]["pdf_url"]
    assert result["evidence_package"]["json_url"]
    assert "citizen" in result["recommendations"]
    assert "officer" in result["recommendations"]
    assert "analyst" in result["recommendations"]


def test_fuse_links_cases_sharing_phone_number(client):
    client.post("/fuse", json={"case_id": "case_1", "scam_result": SCAM_RESULT, "user_report": USER_REPORT})
    resp = client.post("/fuse", json={
        "case_id": "case_2",
        "scam_result": SCAM_RESULT,  # same phone entity
        "user_report": {**USER_REPORT, "reporter_id": "user_2"},
    })
    result = resp.json()["result"]
    linked_ids = [c["case_id"] for c in result["linked_cases"]]
    assert "case_1" in linked_ids
    assert "+919876543210" in result["linked_cases"][0]["shared_entities"]
    assert result["network_analysis"]["size"] >= 2


def test_fuse_validation_error_on_blank_case_id(client):
    resp = client.post("/fuse", json={"case_id": "   "})
    assert resp.status_code == 400
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_fuse_low_risk_no_inputs(client):
    resp = client.post("/fuse", json={"case_id": "case_empty"})
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert result["risk_level"] == "low"
