"""系统信息与健康检查。"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.a2ui.constants import A2UI_PROTOCOL_VERSION
from app.schemas.system import HealthResponse, ServiceInfo

router = APIRouter()


@router.get("/", response_model=ServiceInfo, summary="服务信息")
async def service_info(request: Request) -> ServiceInfo:
    settings = request.app.state.settings
    return ServiceInfo(
        name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        docs=settings.docs_url,
        endpoints={
            "chat": "/api/chat",
            "agui": "/api/agent",
            "a2uiCatalog": "/api/a2ui/catalog",
            "a2uiSurfaces": "/api/a2ui/surfaces",
            "health": "/health",
            "openapi": settings.openapi_url,
        },
    )


@router.get("/health", response_model=HealthResponse, summary="健康检查")
async def health(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    service = request.app.state.a2ui_service
    agent = getattr(request.app.state, "agui_agent", None)

    return HealthResponse(
        status="ok",
        version=settings.app_version,
        environment=settings.environment,
        model={
            "provider": settings.llm_provider,
            "name": settings.active_model_name,
            "configured": settings.model_configured,
        },
        a2ui={
            "protocolVersion": A2UI_PROTOCOL_VERSION,
            "catalogId": settings.a2ui_catalog_id,
            **service.stats(),
            "agent": getattr(agent, "name", None),
        },
        checkpoint={
            "backend": settings.checkpoint_backend,
            "sqlitePath": (
                settings.checkpoint_sqlite_path
                if settings.checkpoint_backend == "sqlite"
                else None
            ),
        },
    )


@router.get("/ready", include_in_schema=False)
async def ready(request: Request) -> dict:
    return {
        "status": "ready",
        "agent": getattr(request.app.state, "agui_agent", None) is not None,
    }
