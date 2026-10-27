"""会话接口模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.a2ui import SurfacePayload
from app.schemas.base import APIModel
from app.schemas.chat import ChatMessage


class ThreadSummary(APIModel):
    thread_id: str
    message_count: int = 0
    surface_count: int = 0
    updated_at: datetime | None = None


class ThreadDetail(APIModel):
    thread_id: str
    messages: list[ChatMessage] = Field(default_factory=list)
    surfaces: list[SurfacePayload] = Field(default_factory=list)
    a2ui_operations: list[dict[str, Any]] = Field(default_factory=list)
