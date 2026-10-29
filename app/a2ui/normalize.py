"""A2UI 操作归一化。

模型生成组件时偶尔会使用 HTML 习惯字段（例如 ``Image.alt``），而 A2UI
Basic Catalog 使用 ``description``。在服务端校验前做最小归一化，避免整条
``updateComponents`` 因单个别名被拒绝，导致前端渲染后又被空 surface 覆盖。
"""

from __future__ import annotations

import copy
from typing import Any


def normalize_component(component: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(component)
    if normalized.get("component") == "Image":
        alt = normalized.pop("alt", None)
        if alt is not None and "description" not in normalized:
            normalized["description"] = alt
    return normalized


def normalize_operation(operation: dict[str, Any]) -> dict[str, Any]:
    """返回归一化后的操作副本，不修改调用方传入的对象。"""

    normalized = copy.deepcopy(operation)
    update = normalized.get("updateComponents")
    if isinstance(update, dict):
        components = update.get("components")
        if isinstance(components, list):
            update["components"] = [
                normalize_component(item) if isinstance(item, dict) else item
                for item in components
            ]
    return normalized
