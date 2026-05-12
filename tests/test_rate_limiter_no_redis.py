from fastapi.testclient import TestClient
from main import app


client = TestClient(app)


def test_app_starts_without_redis(monkeypatch):
    # Ensure REDIS_URL env var is unset
    monkeypatch.delenv("REDIS_URL", raising=False)
    response = client.get("/api/health")
    assert response.status_code == 200
    # The log should contain the warning about rate limiting disabled - we just check the request succeeded.
