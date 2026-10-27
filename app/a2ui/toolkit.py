"""与 ``ag-ui-a2ui-toolkit`` 的桥接。

AG-UI 生态约定：工具结果返回 ``{"a2ui_operations": [...]}``，前端 A2UI
middleware 读取该 key 后把 JSON 渲染成原生 UI。
"""

from __future__ import annotations

import json
from typing import Any

from ag_ui_a2ui_toolkit import (
    A2UI_OPERATIONS_KEY,
    assemble_ops,
    wrap_as_operations_envelope,
)

from app.a2ui.constants import BASIC_CATALOG_ID

__all__ = [
    "A2UI_OPERATIONS_KEY",
    "BASIC_CATALOG_ID",
    "assemble_ops",
    "operations_envelope",
    "parse_operations",
    "parse_tool_content",
]


def operations_envelope(operations: list[dict[str, Any]]) -> str:
    """把操作列表包装为工具结果字符串。"""

    return wrap_as_operations_envelope(operations)


def parse_tool_content(content: Any) -> list[dict[str, Any]]:
    """从 LangChain ToolMessage.content 中提取 A2UI 操作列表。"""

    if isinstance(content, dict):
        operations = content.get(A2UI_OPERATIONS_KEY)
        return operations if isinstance(operations, list) else []

    if isinstance(content, list):
        for block in content:
            if isinstance(block, str):
                parsed = _parse_json_string(block)
                if parsed:
                    return parsed
            elif isinstance(block, dict):
                if block.get("type") == "text" and isinstance(block.get("text"), str):
                    parsed = _parse_json_string(block["text"])
                    if parsed:
                        return parsed
                elif A2UI_OPERATIONS_KEY in block:
                    operations = block[A2UI_OPERATIONS_KEY]
                    return operations if isinstance(operations, list) else []
        return []

    if isinstance(content, str):
        return _parse_json_string(content)

    return []


def parse_operations(payload: Any) -> list[dict[str, Any]]:
    """解析 ``a2ui_operations`` 容器（dict/JSON 字符串）。"""

    if isinstance(payload, dict):
        operations = payload.get(A2UI_OPERATIONS_KEY)
        return operations if isinstance(operations, list) else []
    if isinstance(payload, str):
        return _parse_json_string(payload)
    return []


def _parse_json_string(value: str) -> list[dict[str, Any]]:
    value = value.strip()
    if not value or not value.startswith("{"):
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, dict):
        return []
    operations = parsed.get(A2UI_OPERATIONS_KEY)
    if not isinstance(operations, list):
        return []
    return [item for item in operations if isinstance(item, dict)]
