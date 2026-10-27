from __future__ import annotations

from app.a2ui.constants import BASIC_CATALOG_ID


def test_catalog_endpoints(client):
    response = client.get("/api/a2ui/catalog")
    assert response.status_code == 200
    catalog = response.json()
    assert catalog["catalogId"] == BASIC_CATALOG_ID
    assert "Text" in catalog["components"]

    response = client.get("/api/a2ui/components")
    assert response.status_code == 200
    names = {item["name"] for item in response.json()["components"]}
    assert {"Text", "Button", "TextField", "Column"} <= names

    assert client.get("/api/a2ui/schema").status_code == 200
    assert client.get("/api/a2ui/client-schema").status_code == 200


def test_demo_surface_and_surface_crud(client):
    response = client.get("/api/a2ui/demo", params={"threadId": "demo-thread"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["errors"] == []
    surface_id = payload["surfaceId"]
    assert len(payload["messages"]) == 3

    response = client.get(
        "/api/a2ui/surfaces",
        params={"threadId": "demo-thread"},
    )
    assert response.status_code == 200
    assert [item["surfaceId"] for item in response.json()] == [surface_id]

    response = client.get(
        f"/api/a2ui/surfaces/{surface_id}",
        params={"threadId": "demo-thread"},
    )
    assert response.status_code == 200
    surface = response.json()
    assert surface["surfaceId"] == surface_id
    assert surface["dataModel"]["form"]["name"] == "Alice"
    assert any(item["id"] == "root" for item in surface["components"])

    response = client.delete(
        f"/api/a2ui/surfaces/{surface_id}",
        params={"threadId": "demo-thread"},
    )
    assert response.status_code == 204
    response = client.get(
        f"/api/a2ui/surfaces/{surface_id}",
        params={"threadId": "demo-thread"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "surface_not_found"


def test_apply_messages_strict_and_idempotent(client):
    create = {
        "version": "v0.9",
        "createSurface": {"surfaceId": "manual", "catalogId": BASIC_CATALOG_ID},
    }
    update = {
        "version": "v0.9",
        "updateComponents": {
            "surfaceId": "manual",
            "components": [
                {"id": "root", "component": "Column", "children": ["text"]},
                {"id": "text", "component": "Text", "text": "hello", "variant": "h2"},
            ],
        },
    }
    data = {
        "version": "v0.9",
        "updateDataModel": {
            "surfaceId": "manual",
            "path": "/user",
            "value": {"name": "A"},
        },
    }

    response = client.post(
        "/api/a2ui/messages",
        json={"threadId": "manual-thread", "messages": [create, update, data]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["errors"] == []
    assert body["surfaces"][0]["surfaceId"] == "manual"
    assert body["surfaces"][0]["dataModel"] == {"user": {"name": "A"}}

    # 严格模式重复 createSurface -> 409
    response = client.post(
        "/api/a2ui/messages",
        json={"threadId": "manual-thread", "messages": create, "strict": True},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "surface_already_exists"


def test_apply_messages_rejects_invalid_component(client):
    response = client.post(
        "/api/a2ui/messages",
        json={
            "threadId": "invalid-thread",
            "messages": [
                {
                    "version": "v0.9",
                    "createSurface": {
                        "surfaceId": "invalid",
                        "catalogId": BASIC_CATALOG_ID,
                    },
                },
                {
                    "version": "v0.9",
                    "updateComponents": {
                        "surfaceId": "invalid",
                        "components": [
                            {"id": "root", "component": "ClearlyNotAComponent"}
                        ],
                    },
                },
            ],
        },
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "a2ui_validation_failed"
    assert any(
        issue["code"] == "schema_violation" for issue in body["error"]["details"]
    )


def test_action_endpoint(client):
    demo = client.get("/api/a2ui/demo", params={"threadId": "action-thread"}).json()
    surface_id = demo["surfaceId"]

    response = client.post(
        "/api/a2ui/actions",
        json={
            "threadId": "action-thread",
            "action": {
                "name": "submitDemoForm",
                "surfaceId": surface_id,
                "sourceComponentId": "submit_button",
                "timestamp": "2026-10-27T00:00:00Z",
                "context": {"name": "Alice", "subscribe": True},
            },
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["accepted"] is True
    assert body["action"]["name"] == "submitDemoForm"
    assert body["action"]["threadId"] == "action-thread"

    actions = client.get(
        "/api/a2ui/actions", params={"threadId": "action-thread"}
    ).json()["actions"]
    assert len(actions) == 1
    assert actions[0]["context"]["name"] == "Alice"


def test_action_for_unknown_surface_returns_404(client):
    response = client.post(
        "/api/a2ui/actions",
        json={
            "threadId": "unknown",
            "action": {
                "name": "submit",
                "surfaceId": "does-not-exist",
                "sourceComponentId": "button",
                "timestamp": "2026-10-27T00:00:00Z",
                "context": {},
            },
        },
    )
    assert response.status_code == 404
