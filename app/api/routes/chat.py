"""对话接口。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_chat_service
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat import ChatService

router = APIRouter()


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="非流式对话",
    description=(
        "一次性调用 Agent 并返回最终 assistant 消息。"
        "需要流式 AG-UI 事件时请使用 POST /api/agent。"
    ),
)
async def chat(
    payload: ChatRequest,
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> ChatResponse:
    return await service.chat(payload)
