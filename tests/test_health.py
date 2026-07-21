def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert body["graph_backend"] == "networkx"
    assert body["cases_indexed"] == 0


def test_schema(client):
    resp = client.get("/schema")
    assert resp.status_code == 200
    assert "/fuse" in resp.json()["endpoints"]
