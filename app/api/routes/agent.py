"""AG-UI 协议端点。

请求体为 AG-UI ``RunAgentInput``，响应为 SSE 事件流（增量文本、工具调用、
状态快照、A2UI 工具结果等）。实现基于 ``ag_ui_langgraph.LangGraphAgent``。
"""

from __future__ import annotations

import logging
from typing import Any

from ag_ui.core.types import RunAgentInput
from ag_ui.encoder import EventEncoder
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent")


@router.post(
    "",
    summary="AG-UI Agent SSE 端点",
    description=(
        "兼容 AG-UI 客户端（如 CopilotKit）的标准端点。"
        "使用 SSE 流式返回 TEXT_MESSAGE_*、TOOL_CALL_*、STATE_*、RUN_* 事件。"
    ),
)
async def run_agent(input_data: RunAgentInput, request: Request):
    agent = getattr(request.app.state, "agui_agent", None)
    if agent is None:
        raise HTTPException(status_code=503, detail="AG-UI Agent 尚未初始化")

    encoder = EventEncoder(accept=request.headers.get("accept"))

    async def event_generator():
        # 每个请求 clone 一份，避免并发请求共享 active_run 状态。
        request_agent = agent.clone()
        async for event in request_agent.run(input_data):
            yield encoder.encode(event)

    return StreamingResponse(
        event_generator(),
        media_type=encoder.get_content_type(),
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/health", summary="AG-UI Agent 健康检查")
async def agent_health(request: Request) -> dict[str, Any]:
    agent = getattr(request.app.state, "agui_agent", None)
    if agent is None:
        return {"status": "unavailable", "agent": None}
    return {
        "status": "ok",
        "agent": {
            "name": getattr(agent, "name", None),
            "description": getattr(agent, "description", None),
            "capabilities": agent.get_capabilities(),
        },
    }
