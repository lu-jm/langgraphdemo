from __future__ import annotations

from langchain_core.messages import AIMessage

from tests.helpers import agui_payload, parse_sse


def test_agui_text_stream(client):
    payload = agui_payload(thread_id="agui-text")
    response = client.post(
        "/api/agent",
        json=payload,
        headers={"accept": "text/event-stream"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["x-request-id"]

    events = parse_sse(response.text)
    types = [event["type"] for event in events]
    assert types[0] == "RUN_STARTED"
    assert types[-1] == "RUN_FINISHED"
    assert "MESSAGES_SNAPSHOT" in types
    # 关闭 raw events 后不再输出体积巨大的 RAW 事件
    assert "RAW" not in types


def test_agui_tool_result_contains_a2ui_operations(bundle_factory):
    bundle = bundle_factory(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "render_calculation_card",
                        "args": {"expression": "3 * 3", "result": "9"},
                        "id": "call-agui",
                    }
                ],
            ),
            AIMessage(content="卡片已生成。"),
        ]
    )

    from fastapi.testclient import TestClient

    with TestClient(bundle.app) as client:
        response = client.post(
            "/api/agent",
            json=agui_payload(thread_id="agui-tools", content="渲染 3*3"),
            headers={"accept": "text/event-stream"},
        )
        assert response.status_code == 200
        events = parse_sse(response.text)
        results = [event for event in events if event["type"] == "TOOL_CALL_RESULT"]
        assert results
        assert "a2ui_operations" in results[0]["content"]
        assert bundle.service.list_surfaces("agui-tools")
