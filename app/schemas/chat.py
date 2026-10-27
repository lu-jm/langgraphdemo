"""对话接口模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from app.schemas.a2ui import SurfacePayload
from app.schemas.base import APIModel


class ContextEntry(APIModel):
    description: str | None = None
    value: Any = None


class ChatRequest(APIModel):
    message: str = Field(min_length=1, description="用户输入")
    thread_id: str | None = Field(
        default=None,
        description="会话 ID；不传时由后端生成",
        examples=["thread-demo"],
    )
    context: list[ContextEntry] = Field(
        default_factory=list,
        description="AG-UI 风格的上下文条目，例如前端注入的 catalog/业务上下文",
    )


class ToolCallPayload(APIModel):
    id: str
    name: str
    args: dict[str, Any] = Field(default_factory=dict)


class ChatMessage(APIModel):
    id: str | None = None
    role: Literal["system", "user", "assistant", "tool", "developer"] = "assistant"
    content: Any = ""
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[ToolCallPayload] = Field(default_factory=list)


class ChatResponse(APIModel):
    thread_id: str
    run_id: str
    message: ChatMessage
    tool_calls: list[ToolCallPayload] = Field(default_factory=list)
    a2ui: list[SurfacePayload] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
