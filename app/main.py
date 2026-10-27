"""FastAPI 应用入口。

启动方式：

    uv run uvicorn app.main:app --reload
"""

from __future__ import annotations

import logging
import time
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.a2ui.service import A2UIService
from app.a2ui.store import SurfaceStore
from app.api.router import api_router
from app.api.routes import system
from app.checkpoint import create_checkpointer
from app.config import Settings, get_settings
from app.errors import AppError
from app.logging_config import configure_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    configure_logging(settings.log_level)
    logger.info(
        "启动 %s v%s（env=%s）",
        settings.app_name,
        settings.app_version,
        settings.environment,
    )

    async with AsyncExitStack() as stack:
        if app.state.graph is None:
            checkpointer = await create_checkpointer(settings, stack)
            app.state.checkpointer = checkpointer

            from app.agent.graph import build_graph

            app.state.graph = build_graph(
                settings,
                checkpointer=checkpointer,
                a2ui_service=app.state.a2ui_service,
            )
        else:
            app.state.checkpointer = getattr(app.state.graph, "checkpointer", None)

        if app.state.agui_agent is None:
            from ag_ui_langgraph import LangGraphAgent

            app.state.agui_agent = LangGraphAgent(
                name="langgraph-a2ui-agent",
                description=(
                    "LangGraph Agent，支持工具调用、会话记忆与 A2UI 生成式界面。"
                ),
                graph=app.state.graph,
                emit_raw_events=settings.agui_emit_raw_events,
                emit_subagent_events=settings.agui_emit_subagent_events,
            )

        logger.info("AG-UI 端点已就绪：POST /api/agent")
        try:
            yield
        finally:
            logger.info("正在关闭应用")

    # AsyncExitStack 在此关闭 SQLite 连接等资源。


def create_app(
    settings: Settings | None = None,
    *,
    graph: Any | None = None,
    a2ui_service: A2UIService | None = None,
    agui_agent: Any | None = None,
) -> FastAPI:
    """应用工厂。

    测试时可注入 ``graph`` / ``a2ui_service`` 来替换真实模型与存储。
    """

    settings = settings or get_settings()
    configure_logging(settings.log_level)

    service = a2ui_service or A2UIService(
        default_catalog_id=settings.a2ui_catalog_id,
        store=SurfaceStore(
            max_surfaces_per_thread=settings.a2ui_max_surfaces_per_thread,
            max_actions_per_thread=settings.a2ui_max_actions_per_thread,
        ),
    )

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "基于 LangGraph 的 Agent 后端：FastAPI + AG-UI 流式协议 + A2UI v0.9 "
            "生成式界面。"
        ),
        docs_url=settings.docs_url,
        redoc_url=settings.redoc_url,
        openapi_url=settings.openapi_url,
        lifespan=lifespan,
    )

    app.state.settings = settings
    app.state.a2ui_service = service
    app.state.graph = graph
    app.state.agui_agent = agui_agent
    app.state.checkpointer = getattr(graph, "checkpointer", None)
    app.state.started_at = datetime.now(UTC)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Process-Time-Ms"],
    )

    app.include_router(system.router)
    app.include_router(api_router, prefix="/api")

    _register_middleware(app)
    _register_exception_handlers(app)
    return app


def _register_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = (
            f"{(time.perf_counter() - started) * 1000:.1f}"
        )
        return response


def _error_payload(
    code: str, message: str, details: Any = None, request_id: str | None = None
):
    payload: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details is not None:
        payload["error"]["details"] = details
    if request_id:
        payload["error"]["requestId"] = request_id
    return payload


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(
                exc.code,
                exc.message,
                exc.details,
                getattr(request.state, "request_id", None),
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        errors = [
            {
                "path": ".".join(str(part) for part in error.get("loc", [])),
                "message": error.get("msg", ""),
                "type": error.get("type", ""),
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=_error_payload(
                "request_validation_failed",
                "请求参数校验失败",
                errors,
                getattr(request.state, "request_id", None),
            ),
        )

    @app.exception_handler(HTTPException)
    async def handle_http_error(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(
                "http_error",
                str(exc.detail),
                None,
                getattr(request.state, "request_id", None),
            ),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception):
        logger.exception("未处理异常：%s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content=_error_payload(
                "internal_error",
                "服务器内部错误",
                {"type": type(exc).__name__},
                getattr(request.state, "request_id", None),
            ),
        )


app = create_app()


def run() -> None:
    """控制台入口：``uv run agent-api``。"""

    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run()
