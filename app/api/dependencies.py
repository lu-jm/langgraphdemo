"""FastAPI 依赖。"""

from __future__ import annotations

from fastapi import Request

from app.a2ui.service import A2UIService
from app.config import Settings
from app.errors import ModelNotConfiguredError
from app.services.chat import ChatService
from app.services.threads import ThreadService


def get_settings_from_app(request: Request) -> Settings:
    return request.app.state.settings


def get_a2ui_service(request: Request) -> A2UIService:
    return request.app.state.a2ui_service


def get_graph(request: Request):
    graph = getattr(request.app.state, "graph", None)
    if graph is None:
        raise ModelNotConfiguredError("Agent 尚未初始化")
    return graph


def get_chat_service(request: Request) -> ChatService:
    return ChatService(
        settings=get_settings_from_app(request),
        graph=get_graph(request),
        a2ui_service=get_a2ui_service(request),
    )


def get_thread_service(request: Request) -> ThreadService:
    return ThreadService(
        settings=get_settings_from_app(request),
        graph=get_graph(request),
        a2ui_service=get_a2ui_service(request),
    )
