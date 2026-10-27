from __future__ import annotations

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver

from app.a2ui.service import A2UIService
from app.agent.graph import build_graph
from app.config import Settings
from app.main import create_app


def test_chat_and_thread_lifecycle(client):
    response = client.post(
        "/api/chat",
        json={"message": "你好", "threadId": "chat-thread"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["threadId"] == "chat-thread"
    assert body["message"]["role"] == "assistant"
    assert body["message"]["content"] == "你好，我是测试助手。"
    assert body["a2ui"] == []

    threads = client.get("/api/threads").json()
    assert any(item["threadId"] == "chat-thread" for item in threads)

    detail = client.get("/api/threads/chat-thread")
    assert detail.status_code == 200
    payload = detail.json()
    assert [message["role"] for message in payload["messages"]] == ["user", "assistant"]

    deleted = client.delete("/api/threads/chat-thread")
    assert deleted.status_code == 204
    assert client.get("/api/threads/chat-thread").status_code == 404


def test_chat_with_a2ui_tool_call(bundle_factory):
    bundle = bundle_factory(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "render_calculation_card",
                        "args": {
                            "expression": "2 + 2",
                            "result": "4",
                            "notes": "测试卡片",
                        },
                        "id": "call-1",
                    }
                ],
            ),
            AIMessage(content="已经为你生成结果卡片。"),
        ]
    )

    from fastapi.testclient import TestClient

    with TestClient(bundle.app) as client:
        response = client.post(
            "/api/chat",
            json={
                "message": "把 2+2 的结果渲染成卡片",
                "threadId": "a2ui-chat",
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["message"]["content"] == "已经为你生成结果卡片。"
        assert len(body["a2ui"]) == 1
        surface = body["a2ui"][0]
        assert surface["surfaceId"].startswith("calc-")
        assert surface["dataModel"]["result"] == "4"

        detail = client.get("/api/threads/a2ui-chat").json()
        assert len(detail["surfaces"]) == 1
        assert len(detail["a2uiOperations"]) == 3
        assert (
            detail["a2uiOperations"][0]["createSurface"]["surfaceId"]
            == surface["surfaceId"]
        )


def test_thread_not_found(client):
    response = client.get("/api/threads/nope")
    assert response.status_code == 404


def test_chat_without_api_key_returns_503():
    settings = Settings(
        _env_file=None,
        environment="test",
        zhipuai_api_key="",
        log_level="WARNING",
        checkpoint_backend="memory",
    )
    service = A2UIService()
    # 模拟“没有模型 Key”的图：显式让 build_graph 不创建模型。
    graph = build_graph(
        settings,
        checkpointer=MemorySaver(),
        model=None,
        a2ui_service=service,
    )
    app = create_app(settings, graph=graph, a2ui_service=service)

    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        response = client.post("/api/chat", json={"message": "你好"})
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "model_not_configured"
