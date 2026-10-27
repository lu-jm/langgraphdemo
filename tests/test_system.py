from __future__ import annotations


def test_root_service_info(client):
    response = client.get("/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["name"]
    assert payload["endpoints"]["chat"] == "/api/chat"
    assert payload["endpoints"]["agui"] == "/api/agent"


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["a2ui"]["protocolVersion"] == "0.9"
    assert payload["model"]["configured"] is True
    assert payload["checkpoint"]["backend"] == "memory"


def test_agui_health(client):
    response = client.get("/api/agent/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["agent"]["name"] == "langgraph-a2ui-agent"
    assert payload["agent"]["capabilities"]["humanInTheLoop"]["supported"] is True


def test_openapi_available(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    for path in (
        "/api/chat",
        "/api/agent",
        "/api/threads/{thread_id}",
        "/api/a2ui/catalog",
        "/api/a2ui/surfaces",
        "/api/a2ui/messages",
        "/api/a2ui/actions",
    ):
        assert path in paths
