"""对话服务：封装 LangGraph 调用与响应转换。"""

from __future__ import annotations

import logging
from uuid import uuid4

from langchain_core.messages import HumanMessage
from langgraph.errors import GraphRecursionError

from app.a2ui.service import A2UIService
from app.config import Settings
from app.errors import ModelNotConfiguredError, UpstreamError
from app.schemas.a2ui import SurfacePayload
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.serializers import last_ai_message, serialize_message

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(
        self,
        *,
        settings: Settings,
        graph,
        a2ui_service: A2UIService,
    ) -> None:
        self.settings = settings
        self.graph = graph
        self.a2ui_service = a2ui_service

    def new_thread_id(self) -> str:
        return f"thread-{uuid4().hex[:12]}"

    async def chat(self, request: ChatRequest) -> ChatResponse:
        thread_id = request.thread_id or self.new_thread_id()
        run_id = f"run-{uuid4().hex[:12]}"

        initial_state: dict = {
            "messages": [HumanMessage(content=request.message)],
        }
        if request.context:
            initial_state["ag-ui"] = {
                "context": [
                    entry.model_dump(exclude_none=True) for entry in request.context
                ]
            }

        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": self.settings.agent_recursion_limit,
        }

        try:
            result = await self.graph.ainvoke(initial_state, config)
        except ModelNotConfiguredError:
            raise
        except GraphRecursionError as exc:
            raise UpstreamError(
                "Agent 达到最大推理步数，请简化问题后重试。",
                details={"recursionLimit": self.settings.agent_recursion_limit},
            ) from exc
        except Exception as exc:  # pragma: no cover - 依赖外部模型
            if "api key" in str(exc).lower() or "api_key" in str(exc).lower():
                raise ModelNotConfiguredError() from exc
            logger.exception("Agent 调用失败（thread=%s）", thread_id)
            raise UpstreamError(
                "Agent 调用失败，请稍后重试。",
                details={"error": type(exc).__name__},
            ) from exc

        messages = result.get("messages", []) if isinstance(result, dict) else []
        ai_message = last_ai_message(messages)
        if ai_message is None:
            raise UpstreamError("Agent 未返回 assistant 消息")

        surfaces = [
            SurfacePayload.from_surface(surface)
            for surface in self.a2ui_service.list_surfaces(thread_id)
        ]

        return ChatResponse(
            thread_id=thread_id,
            run_id=run_id,
            message=serialize_message(ai_message),
            tool_calls=serialize_message(ai_message).tool_calls,
            a2ui=surfaces,
        )

    async def forward_a2ui_action(
        self,
        *,
        thread_id: str,
        action: dict,
    ) -> ChatResponse:
        """把客户端 A2UI action 转成一条用户消息交给 Agent。"""

        context = action.get("context") or {}
        message = (
            "用户在 A2UI 界面上执行了操作。\n"
            f"action: {action.get('name')}\n"
            f"surfaceId: {action.get('surfaceId')}\n"
            f"context: {context}\n"
            "请根据该操作继续处理；如果不需要更新界面，直接用文本回复。"
        )
        return await self.chat(ChatRequest(message=message, thread_id=thread_id))
