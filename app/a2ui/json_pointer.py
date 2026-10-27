"""JSON Pointer（RFC 6901）读写工具。

A2UI 的 ``updateDataModel.path`` 使用 JSON Pointer。协议还规定 ``"/"``
表示整个数据模型根节点，因此这里对 ``""`` 与 ``"/"`` 做同等处理。
"""

from __future__ import annotations

import copy
from typing import Any

_MISSING = object()


class JsonPointerError(ValueError):
    """非法的 JSON Pointer 或路径无法访问。"""


def is_root(pointer: str | None) -> bool:
    return pointer in (None, "", "/")


def parse_pointer(pointer: str) -> list[str]:
    """把 JSON Pointer 解析为 token 列表。"""

    if is_root(pointer):
        return []
    if not pointer.startswith("/"):
        raise JsonPointerError(f"JSON Pointer 必须以 '/' 开头：{pointer!r}")
    return [
        token.replace("~1", "/").replace("~0", "~") for token in pointer.split("/")[1:]
    ]


def _is_array_index(token: str) -> bool:
    return token.isdigit() or token == "-"


def get_value(document: Any, pointer: str | None, default: Any = None) -> Any:
    """读取指针位置的值，不存在时返回 ``default``。"""

    current = document
    for token in parse_pointer(pointer):
        if isinstance(current, dict):
            if token not in current:
                return default
            current = current[token]
        elif isinstance(current, list):
            if token == "-":
                return default
            try:
                index = int(token)
                current = current[index]
            except (ValueError, IndexError):
                return default
        else:
            return default
    return current


def set_value(document: Any, pointer: str | None, value: Any) -> Any:
    """写入指针位置的值并返回根节点。

    根节点写入会直接返回 ``value``（调用方负责替换整个数据模型）。
    """

    tokens = parse_pointer(pointer)
    if not tokens:
        return copy.deepcopy(value)

    root = document
    if root is None:
        root = [] if _is_array_index(tokens[0]) else {}
    if not isinstance(root, (dict, list)):
        raise JsonPointerError("数据模型根节点必须是 object 或 array")

    current = root
    for position, token in enumerate(tokens[:-1]):
        next_token = tokens[position + 1]
        if isinstance(current, dict):
            child = current.get(token, _MISSING)
            if child is _MISSING or not isinstance(child, (dict, list)):
                child = [] if _is_array_index(next_token) else {}
                current[token] = child
            current = child
        elif isinstance(current, list):
            index = _resolve_list_index(current, token, create=True)
            child = current[index]
            if not isinstance(child, (dict, list)):
                child = [] if _is_array_index(next_token) else {}
                current[index] = child
            current = child
        else:  # pragma: no cover - 由父级保证
            raise JsonPointerError("路径经过非容器节点")

    last = tokens[-1]
    if isinstance(current, dict):
        current[last] = copy.deepcopy(value)
    elif isinstance(current, list):
        index = _resolve_list_index(current, last, create=True)
        current[index] = copy.deepcopy(value)
    else:  # pragma: no cover
        raise JsonPointerError("父节点不是容器")
    return root


def remove_value(document: Any, pointer: str | None) -> Any:
    """删除指针位置的值并返回根节点。"""

    tokens = parse_pointer(pointer)
    if not tokens:
        return {}

    parent = document
    for token in tokens[:-1]:
        if isinstance(parent, dict):
            if token not in parent:
                return document
            parent = parent[token]
        elif isinstance(parent, list):
            try:
                parent = parent[int(token)]
            except (ValueError, IndexError):
                return document
        else:
            return document

    last = tokens[-1]
    if isinstance(parent, dict):
        parent.pop(last, None)
    elif isinstance(parent, list):
        try:
            index = int(last)
            if 0 <= index < len(parent):
                parent.pop(index)
        except (ValueError, IndexError):
            pass
    return document


def _resolve_list_index(items: list[Any], token: str, *, create: bool) -> int:
    if token == "-":
        if create:
            items.append(None)
            return len(items) - 1
        raise JsonPointerError("'-' 只能用于写入数组末尾")
    try:
        index = int(token)
    except ValueError as exc:
        raise JsonPointerError(f"数组索引必须是整数：{token!r}") from exc
    if index < 0:
        raise JsonPointerError("数组索引不能为负数")
    if create:
        while len(items) <= index:
            items.append(None)
        return index
    if index >= len(items):
        raise JsonPointerError(f"数组索引越界：{index}")
    return index
