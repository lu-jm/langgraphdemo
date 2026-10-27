"""A2UI 协议接口。"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Path, Query, Response, status

from app.a2ui.builder import demo_surface
from app.a2ui.catalog import (
    component_summary,
    get_catalog_for_client,
    load_client_schema,
    load_server_schema,
)
from app.a2ui.service import A2UIService
from app.api.dependencies import get_a2ui_service, get_chat_service
from app.schemas.a2ui import (
    A2UIActionRequest,
    A2UIActionResponse,
    A2UIApplyRequest,
    A2UIApplyResponse,
    SurfacePayload,
    SurfaceSummary,
)
from app.services.chat import ChatService

router = APIRouter(prefix="/a2ui")


@router.get("/catalog", summary="获取 A2UI Basic Catalog")
async def get_catalog() -> dict[str, Any]:
    return get_catalog_for_client()


@router.get("/components", summary="获取组件清单（简要）")
async def list_components() -> dict[str, Any]:
    catalog = get_catalog_for_client()
    return {
        "catalogId": catalog.get("catalogId"),
        "components": component_summary(),
    }


@router.get("/schema", summary="获取 A2UI 服务端 JSON Schema")
async def get_server_schema() -> dict[str, Any]:
    return load_server_schema()


@router.get("/client-schema", summary="获取 A2UI 客户端事件 JSON Schema")
async def get_client_schema() -> dict[str, Any]:
    return load_client_schema()


@router.get(
    "/surfaces",
    response_model=list[SurfaceSummary],
    summary="列出线程下的 A2UI surface",
)
async def list_surfaces(
    service: Annotated[A2UIService, Depends(get_a2ui_service)],
    thread_id: Annotated[str, Query(alias="threadId", max_length=128)] = "default",
) -> list[SurfaceSummary]:
    return [
        SurfaceSummary.from_surface(surface)
        for surface in service.list_surfaces(thread_id)
    ]


@router.get(
    "/surfaces/{surface_id}",
    response_model=SurfacePayload,
    summary="获取单个 A2UI surface",
)
async def get_surface(
    surface_id: Annotated[str, Path(min_length=1)],
    service: Annotated[A2UIService, Depends(get_a2ui_service)],
    thread_id: Annotated[str, Query(alias="threadId", max_length=128)] = "default",
) -> SurfacePayload:
    return SurfacePayload.from_surface(service.get_surface(thread_id, surface_id))


@router.delete(
    "/surfaces/{surface_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除 A2UI surface",
)
async def delete_surface(
    surface_id: Annotated[str, Path(min_length=1)],
    service: Annotated[A2UIService, Depends(get_a2ui_service)],
    thread_id: Annotated[str, Query(alias="threadId", max_length=128)] = "default",
) -> Response:
    service.delete_surface(thread_id, surface_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/messages",
    response_model=A2UIApplyResponse,
    summary="应用 A2UI 服务端消息",
    description=(
        "用于前端/调试工具直接推送 createSurface、updateComponents、"
        "updateDataModel、deleteSurface 消息。消息会经过官方 JSON Schema 与组件图校验。"
    ),
)
async def apply_messages(
    payload: A2UIApplyRequest,
    service: Annotated[A2UIService, Depends(get_a2ui_service)],
) -> A2UIApplyResponse:
    messages = (
        payload.messages if isinstance(payload.messages, list) else [payload.messages]
    )

    if payload.strict:
        result = service.apply_many(payload.thread_id, messages, strict=True)
        return A2UIApplyResponse(
            surfaces=[
                SurfacePayload.from_surface(item) for item in result.surfaces.values()
            ],
            warnings=result.to_dict()["warnings"],
        )

    operations = [message.to_envelope() for message in messages]
    result = service.apply_operations(payload.thread_id, operations, strict=False)
    return A2UIApplyResponse(
        surfaces=[
            SurfacePayload.from_surface(item) for item in result.surfaces.values()
        ],
        warnings=result.to_dict()["warnings"],
        errors=result.errors,
    )


@router.post(
    "/actions",
    response_model=A2UIActionResponse,
    summary="接收 A2UI 客户端 action",
    description=(
        "接收用户与 surface 交互产生的 action（按钮点击、表单提交等）。"
        "默认只记录 action；forwardToAgent=true 时会把它转成一条用户消息交给 Agent。"
    ),
)
async def receive_action(
    payload: A2UIActionRequest,
    service: Annotated[A2UIService, Depends(get_a2ui_service)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
) -> A2UIActionResponse:
    recorded = service.record_action(payload.thread_id, payload.action)
    surfaces = [
        SurfacePayload.from_surface(surface)
        for surface in service.list_surfaces(payload.thread_id)
    ]

    chat_response = None
    if payload.forward_to_agent:
        chat_response = await chat_service.forward_a2ui_action(
            thread_id=payload.thread_id,
            action=recorded,
        )
        surfaces = chat_response.a2ui

    return A2UIActionResponse(
        accepted=True,
        action=recorded,
        surfaces=surfaces,
        chat=chat_response,
    )


@router.get("/actions", summary="列出最近收到的 A2UI actions")
async def list_actions(
    service: Annotated[A2UIService, Depends(get_a2ui_service)],
    thread_id: Annotated[str, Query(alias="threadId", max_length=128)] = "default",
) -> dict[str, Any]:
    return {
        "threadId": thread_id,
        "actions": service.list_actions(thread_id),
    }


@router.get(
    "/demo",
    summary="生成一个 A2UI 联调 surface",
    description="返回可直接交给 A2UI 前端渲染的完整消息序列，并写入 surface store。",
)
async def demo(
    service: Annotated[A2UIService, Depends(get_a2ui_service)],
    thread_id: Annotated[str, Query(alias="threadId", max_length=128)] = "demo",
) -> dict[str, Any]:
    surface_id = f"demo-{uuid4().hex[:8]}"
    operations = demo_surface(surface_id)
    result = service.apply_operations(thread_id, operations, strict=False)
    return {
        "threadId": thread_id,
        "surfaceId": surface_id,
        "messages": operations,
        "surfaces": [surface.to_dict() for surface in result.surfaces.values()],
        "warnings": [warning.to_dict() for warning in result.warnings],
        "errors": result.errors,
    }
