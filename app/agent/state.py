"""Agent 状态定义。

除了 ``messages``，还保留：

- ``a2ui``：最近一次工具调用产生的 A2UI 操作列表，会随 AG-UI
  ``STATE_SNAPSHOT`` 下发给前端；
- ``ag-ui`` / ``tools``：``ag_ui_langgraph`` 适配器注入的上下文与前端工具，
  使用函数式 TypedDict 以支持带连字符的 key。
"""

from __future__ import annotations

from typing import Annotated, Any

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

AgentState = TypedDict(
    "AgentState",
    {
        "messages": Annotated[list[AnyMessage], add_messages],
        "a2ui": list[dict[str, Any]],
        "tools": list[Any],
        "ag-ui": dict[str, Any],
    },
    total=False,
)
