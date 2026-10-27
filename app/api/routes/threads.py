"""会话查询与删除。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response, status

from app.api.dependencies import get_thread_service
from app.schemas.threads import ThreadDetail, ThreadSummary
from app.services.threads import ThreadService

router = APIRouter()


@router.get(
    "/threads",
    response_model=list[ThreadSummary],
    summary="列出会话",
)
async def list_threads(
    service: Annotated[ThreadService, Depends(get_thread_service)],
) -> list[ThreadSummary]:
    return await service.list_threads()


@router.get(
    "/threads/{thread_id}",
    response_model=ThreadDetail,
    summary="获取会话消息与 A2UI surfaces",
)
async def get_thread(
    thread_id: Annotated[str, Path(min_length=1, max_length=128)],
    service: Annotated[ThreadService, Depends(get_thread_service)],
) -> ThreadDetail:
    return await service.get_thread(thread_id)


@router.delete(
    "/threads/{thread_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除会话及其 A2UI surfaces",
)
async def delete_thread(
    thread_id: Annotated[str, Path(min_length=1, max_length=128)],
    service: Annotated[ThreadService, Depends(get_thread_service)],
) -> Response:
    await service.delete_thread(thread_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
