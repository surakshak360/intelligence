from tests.test_fuse import SCAM_RESULT, USER_REPORT


def test_job_not_found(client):
    resp = client.get("/jobs/job_doesnotexist")
    assert resp.status_code == 404


def test_job_poll_after_fuse(client):
    fuse_resp = client.post("/fuse", json={"case_id": "case_1", "scam_result": SCAM_RESULT, "user_report": USER_REPORT})
    job_id = fuse_resp.json()["job_id"]
    resp = client.get(f"/jobs/{job_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["result"]["case_id"] == "case_1"
