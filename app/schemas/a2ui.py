"""A2UI 接口模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from app.a2ui.models import A2UIClientAction, A2UIMessage
from app.a2ui.store import Surface
from app.schemas.base import APIModel


class SurfacePayload(APIModel):
    thread_id: str
    surface_id: str
    catalog_id: str
    theme: dict[str, Any] | None = None
    send_data_model: bool = False
    components: list[dict[str, Any]] = Field(default_factory=list)
    data_model: Any = Field(default_factory=dict)
    revision: int = 0
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_surface(cls, surface: Surface) -> SurfacePayload:
        return cls.model_validate(surface.to_dict())


class SurfaceSummary(APIModel):
    thread_id: str
    surface_id: str
    catalog_id: str
    component_count: int
    revision: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_surface(cls, surface: Surface) -> SurfaceSummary:
        return cls.model_validate(surface.to_summary())


class A2UIApplyRequest(APIModel):
    thread_id: str = Field(default="default", description="会话/线程 ID")
    messages: A2UIMessage | list[A2UIMessage] = Field(
        description="单条或多条 A2UI 消息"
    )
    strict: bool = Field(
        default=True,
        description="严格模式下重复 createSurface 会返回 409；工具同步时使用非严格模式",
    )


class A2UIApplyResponse(APIModel):
    surfaces: list[SurfacePayload] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)


class A2UIActionRequest(APIModel):
    thread_id: str = Field(default="default")
    action: A2UIClientAction
    forward_to_agent: bool = Field(
        default=False,
        description="是否把 action 转发给 Agent 继续处理（需要配置模型）",
    )


class A2UIActionResponse(APIModel):
    accepted: bool = True
    action: dict[str, Any]
    surfaces: list[SurfacePayload] = Field(default_factory=list)
    chat: Any | None = Field(
        default=None,
        description="forward_to_agent=true 时返回的 ChatResponse",
    )
