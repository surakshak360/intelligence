from tests.test_fuse import SCAM_RESULT, USER_REPORT


def test_hotspots_empty(client):
    resp = client.get("/hotspots")
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert result["clusters"] == []
    assert result["heatmap_data"] == []


def test_hotspots_forms_cluster_from_nearby_cases(client):
    base = USER_REPORT["location"]
    for i in range(3):
        loc = {**base, "lat": base["lat"] + i * 0.001, "lng": base["lng"] + i * 0.001}
        client.post("/fuse", json={
            "case_id": f"case_{i}",
            "scam_result": SCAM_RESULT,
            "user_report": {**USER_REPORT, "reporter_id": f"user_{i}", "location": loc},
        })

    resp = client.get("/hotspots", params={"state": "Maharashtra"})
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert len(result["clusters"]) == 1
    assert result["clusters"][0]["case_count"] == 3
    assert len(result["heatmap_data"]) == 3
