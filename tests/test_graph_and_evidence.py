from tests.test_fuse import SCAM_RESULT, USER_REPORT


def test_graph_query_not_found(client):
    resp = client.post("/graph/query", json={"entity_type": "PhoneNumber", "entity_id": "+910000000000", "depth": 1})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_graph_query_after_fuse(client):
    client.post("/fuse", json={"case_id": "case_1", "scam_result": SCAM_RESULT, "user_report": USER_REPORT})
    resp = client.post("/graph/query", json={"entity_type": "Case", "entity_id": "case_1", "depth": 2})
    assert resp.status_code == 200
    result = resp.json()["result"]
    labels = {n["label"] for n in result["nodes"]}
    assert "Case" in labels
    assert "PhoneNumber" in labels


def test_evidence_generate_requires_prior_fuse(client):
    resp = client.post("/evidence/generate", json={"case_id": "never_fused", "format": "json"})
    assert resp.status_code == 404


def test_evidence_generate_after_fuse(client):
    client.post("/fuse", json={"case_id": "case_1", "scam_result": SCAM_RESULT, "user_report": USER_REPORT})
    resp = client.post("/evidence/generate", json={"case_id": "case_1", "format": "both"})
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert result["pdf_url"] and result["pdf_url"].endswith(".pdf")
    assert result["json_url"] and result["json_url"].endswith(".json")
    assert len(result["timeline"]) >= 2
