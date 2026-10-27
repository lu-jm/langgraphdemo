"""LangChain message -> API 模型。"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage

from app.schemas.chat import ChatMessage, ToolCallPayload

_ROLE_MAP = {
    "human": "user",
    "ai": "assistant",
    "system": "system",
    "tool": "tool",
    "developer": "developer",
}


def serialize_message(message: Any) -> ChatMessage:
    role = _ROLE_MAP.get(getattr(message, "type", ""), "assistant")
    content = getattr(message, "content", "")
    if not isinstance(content, (str, list, dict, int, float, bool, type(None))):
        content = str(content)

    tool_calls: list[ToolCallPayload] = []
    if isinstance(message, AIMessage):
        for call in getattr(message, "tool_calls", []) or []:
            tool_calls.append(
                ToolCallPayload(
                    id=str(call.get("id", "")),
                    name=str(call.get("name", "")),
                    args=call.get("args") if isinstance(call.get("args"), dict) else {},
                )
            )

    return ChatMessage(
        id=getattr(message, "id", None),
        role=role,  # type: ignore[arg-type]
        content=content,
        name=getattr(message, "name", None),
        tool_call_id=getattr(message, "tool_call_id", None),
        tool_calls=tool_calls,
    )


def serialize_messages(messages: list[Any]) -> list[ChatMessage]:
    return [serialize_message(message) for message in messages]


def last_ai_message(messages: list[Any]) -> Any | None:
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            return message
    return None
