"""LangGraph Agent 构建。"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AnyMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.a2ui.constants import DEFAULT_THREAD_ID
from app.a2ui.service import A2UIService
from app.a2ui.toolkit import parse_tool_content
from app.agent.llm import build_chat_model, try_build_chat_model
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.state import AgentState
from app.agent.tools import build_agent_tools
from app.config import Settings

logger = logging.getLogger(__name__)


def build_graph(
    settings: Settings,
    *,
    checkpointer: BaseCheckpointSaver | None = None,
    model: Any | None = None,
    a2ui_service: A2UIService | None = None,
):
    """构建并编译 Agent 图。

    Args:
        settings: 应用配置。
        checkpointer: LangGraph checkpointer；传入 ``MemorySaver`` 可启用会话记忆。
        model: 可注入的 ChatModel（测试时使用 FakeModel）。
        a2ui_service: A2UI 服务；工具产生的 surface 会被同步到该服务。
    """

    service = a2ui_service or A2UIService(default_catalog_id=settings.a2ui_catalog_id)
    chat_model = model or try_build_chat_model(settings)
    tools = build_agent_tools(settings, chat_model)
    tools_by_name = {getattr(item, "name", ""): item for item in tools}

    logger.info(
        "Agent 已配置工具：%s",
        ", ".join(sorted(name for name in tools_by_name if name)),
    )

    def _context_prompt(state: AgentState) -> str:
        """把 AG-UI 注入的普通 context 合并进系统提示词。"""

        entries = (state.get("ag-ui") or {}).get("context") or []
        if not entries:
            return ""
        lines = ["", "## 前端上下文"]
        for entry in entries:
            if isinstance(entry, dict):
                description = entry.get("description") or ""
                value = entry.get("value")
            else:
                description = getattr(entry, "description", "") or ""
                value = getattr(entry, "value", None)
            if description or value:
                lines.append(f"- {description}: {value}")
        return "\n".join(lines)

    async def agent_node(state: AgentState, config: RunnableConfig):
        active_model = chat_model or build_chat_model(settings)
        bound_model = active_model.bind_tools(
            tools,
            parallel_tool_calls=settings.agent_parallel_tool_calls,
        )
        messages: list[AnyMessage] = []
        system_content = SYSTEM_PROMPT + _context_prompt(state)
        messages.append(SystemMessage(content=system_content))
        messages.extend(state.get("messages", []))

        response = await bound_model.ainvoke(messages, config)
        return {"messages": [response]}

    async def sync_a2ui_node(state: AgentState, config: RunnableConfig):
        """把本轮工具产生的 ``a2ui_operations`` 同步到后端 surface store。"""

        thread_id = (config or {}).get("configurable", {}).get(
            "thread_id"
        ) or DEFAULT_THREAD_ID
        operations: list[dict[str, Any]] = []
        for message in reversed(state.get("messages", [])):
            if not isinstance(message, ToolMessage):
                break
            operations.extend(parse_tool_content(message.content))

        if not operations:
            return {}

        result = service.apply_operations(thread_id, operations, strict=False)
        if result.errors:
            logger.warning(
                "本轮有 %d 条 A2UI 操作未能应用（thread=%s）",
                len(result.errors),
                thread_id,
            )
        logger.info(
            "已同步 %d 条 A2UI 操作到 thread=%s，surfaces=%s",
            len(operations),
            thread_id,
            list(result.surfaces),
        )
        return {"a2ui": operations}

    builder = StateGraph(AgentState)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", ToolNode(tools))
    builder.add_node("sync_a2ui", sync_a2ui_node)

    builder.add_edge(START, "agent")
    builder.add_conditional_edges(
        "agent", tools_condition, {"tools": "tools", END: END}
    )
    builder.add_edge("tools", "sync_a2ui")
    builder.add_edge("sync_a2ui", "agent")

    return builder.compile(checkpointer=checkpointer)
