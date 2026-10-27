from __future__ import annotations

import json
from typing import Any

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel


class FakeToolChatModel(FakeMessagesListChatModel):
    """支持 bind_tools 的假模型，用于离线测试。"""

    def bind_tools(self, tools, **kwargs):
        return self


def parse_sse(text: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in text.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: ") :]))
    return events


def agui_payload(
    *,
    thread_id: str = "agui-thread",
    content: str = "你好",
    run_id: str = "run-test",
) -> dict[str, Any]:
    return {
        "threadId": thread_id,
        "runId": run_id,
        "state": {},
        "messages": [{"id": "msg-1", "role": "user", "content": content}],
        "tools": [],
        "context": [],
        "forwardedProps": {},
    }
