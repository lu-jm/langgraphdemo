"""A2UI 相关工具。

提供两类能力：

1. ``render_calculation_card``：后端用代码固定 schema，只把数据交给 A2UI
   渲染（fixed-schema generative UI）。
2. ``generate_a2ui``：由 ``ag_ui_langgraph.get_a2ui_tools`` 提供的子 Agent，
   根据自然语言动态生成完整 A2UI surface。
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool, tool

from app.a2ui.builder import SurfaceBuilder
from app.a2ui.constants import BASIC_CATALOG_ID
from app.a2ui.toolkit import operations_envelope
from app.agent.tools.math import add, multiply
from app.config import Settings

logger = logging.getLogger(__name__)


@tool
def render_calculation_card(expression: str, result: str, notes: str = "") -> str:
    """把一个计算结果渲染成 A2UI 卡片（含标题、表达式、结果和复制按钮）。

    仅在用户明确希望看到可视化结果卡片时调用。``expression`` 是表达式，
    ``result`` 是计算后的结果，``notes`` 是可选的补充说明。
    """

    surface_id = f"calc-{uuid4().hex[:8]}"
    builder = SurfaceBuilder(
        surface_id,
        catalog_id=BASIC_CATALOG_ID,
        theme={"primaryColor": "#2563EB", "agentDisplayName": "LangGraph Agent"},
        send_data_model=True,
    )

    children = ["title", "expression", "divider", "result"]
    if notes:
        children.append("notes")
    children.append("hint")

    builder.card("root", "content")
    builder.column("content", [*children, "actions"])
    builder.text("title", "计算结果", variant="h2")
    builder.text("expression", {"path": "/expression"}, variant="caption")
    builder.divider("divider")
    builder.text("result", {"path": "/result"}, variant="h1")
    if notes:
        builder.text("notes", {"path": "/notes"}, variant="body")
    builder.text("hint", "由 LangGraph Agent 通过 A2UI 生成", variant="caption")

    builder.row("actions", ["copy_button"], justify="end")
    builder.text("copy_button_text", "复制结果")
    builder.button(
        "copy_button",
        "copy_button_text",
        variant="borderless",
        action={
            "event": {
                "name": "copyResult",
                "context": {"result": {"path": "/result"}},
            }
        },
    )

    operations = builder.build_ops(
        data={
            "expression": expression,
            "result": result,
            "notes": notes,
            "surfaceId": surface_id,
        }
    )
    return operations_envelope(operations)


def build_agent_tools(
    settings: Settings, model: BaseChatModel | None
) -> list[BaseTool]:
    """构造 Agent 绑定的工具列表。"""

    tools: list[BaseTool] = [add, multiply, render_calculation_card]

    if model is not None and settings.enable_dynamic_a2ui:
        try:
            from ag_ui_langgraph import get_a2ui_tools

            generate_a2ui = get_a2ui_tools(
                {
                    "model": model,
                    "default_catalog_id": settings.a2ui_catalog_id,
                    "guidelines": {
                        "composition_guide": (
                            "## 语言要求\n"
                            "界面中的所有文案（标题、标签、按钮、说明）使用简体中文，"
                            "除非用户明确要求其他语言。\n"
                            "surfaceId 使用小写英文和连字符。"
                        )
                    },
                }
            )
            tools.append(generate_a2ui)
        except Exception:  # pragma: no cover - 依赖版本/模型能力差异
            logger.exception("初始化动态 A2UI 工具失败，将仅提供固定模板工具")
    else:
        logger.info("动态 A2UI 工具未启用（model=%s）", model)

    return tools


def available_tool_names(tools: list[Any]) -> list[str]:
    return [getattr(item, "name", type(item).__name__) for item in tools]
