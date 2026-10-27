"""A2UI（Agent to UI）协议实现。

包含：

- v0.9 消息模型与官方 JSON Schema 校验
- Surface 构建器、内存存储与业务服务
- 与 AG-UI / ``ag_ui_langgraph`` 工具结果约定的桥接
"""

from app.a2ui.builder import SurfaceBuilder, demo_surface
from app.a2ui.constants import (
    A2UI_OPERATIONS_KEY,
    A2UI_PROTOCOL_VERSION,
    A2UI_VERSION,
    BASIC_CATALOG_ID,
)
from app.a2ui.exceptions import (
    A2UIValidationError,
    InvalidActionError,
    SurfaceAlreadyExistsError,
    SurfaceNotFoundError,
)
from app.a2ui.models import (
    A2UIClientAction,
    A2UIMessage,
    Component,
    CreateSurfacePayload,
    DeleteSurfacePayload,
    UpdateComponentsPayload,
    UpdateDataModelPayload,
)
from app.a2ui.service import A2UIService, ApplyResult
from app.a2ui.store import Surface, SurfaceStore

__all__ = [
    "A2UI_OPERATIONS_KEY",
    "A2UI_PROTOCOL_VERSION",
    "A2UI_VERSION",
    "BASIC_CATALOG_ID",
    "A2UIClientAction",
    "A2UIMessage",
    "A2UIService",
    "A2UIValidationError",
    "ApplyResult",
    "Component",
    "CreateSurfacePayload",
    "DeleteSurfacePayload",
    "InvalidActionError",
    "Surface",
    "SurfaceAlreadyExistsError",
    "SurfaceBuilder",
    "SurfaceNotFoundError",
    "SurfaceStore",
    "UpdateComponentsPayload",
    "UpdateDataModelPayload",
    "demo_surface",
]
