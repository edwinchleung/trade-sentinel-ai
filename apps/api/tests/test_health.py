from fastapi.testclient import TestClient

from trade_sentinel_api.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "llm_provider" in data
    assert "llm_configured" in data
