"""A2UI 消息与组件图校验。"""

from __future__ import annotations

import copy
from collections.abc import Iterable
from functools import lru_cache
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from app.a2ui.catalog import (
    BASIC_CATALOG_ID,
    component_names,
    load_basic_catalog,
    load_common_types,
    load_server_schema,
)
from app.a2ui.constants import A2UI_VERSION
from app.a2ui.exceptions import A2UIValidationError, ValidationIssue

_SPEC_BASE = "https://a2ui.org/specification/v0_9/"


def _pointer(parts: Iterable[Any]) -> str:
    segments = [str(part) for part in parts]
    if not segments:
        return "/"
    escaped = [part.replace("~", "~0").replace("/", "~1") for part in segments]
    return "/" + "/".join(escaped)


def _permissive_catalog() -> dict[str, Any]:
    catalog = copy.deepcopy(load_basic_catalog())
    catalog["$defs"]["anyComponent"] = {
        "type": "object",
        "required": ["id", "component"],
        "properties": {
            "id": {"type": "string", "minLength": 1},
            "component": {"type": "string", "minLength": 1},
        },
        "additionalProperties": True,
    }
    catalog["$defs"]["theme"] = {
        "type": "object",
        "additionalProperties": True,
    }
    return catalog


@lru_cache(maxsize=4)
def _validator(catalog_id: str) -> Draft202012Validator:
    schema = copy.deepcopy(load_server_schema())
    common = copy.deepcopy(load_common_types())
    if catalog_id == BASIC_CATALOG_ID or not catalog_id:
        catalog = copy.deepcopy(load_basic_catalog())
    else:
        catalog = _permissive_catalog()

    # server_to_client.json 使用相对引用 "catalog.json"；注册时统一到该 URI。
    catalog["$id"] = _SPEC_BASE + "catalog.json"
    registry = Registry().with_resources(
        [
            (
                _SPEC_BASE + "server_to_client.json",
                Resource.from_contents(schema, default_specification=DRAFT202012),
            ),
            (
                _SPEC_BASE + "common_types.json",
                Resource.from_contents(common, default_specification=DRAFT202012),
            ),
            (
                _SPEC_BASE + "catalog.json",
                Resource.from_contents(catalog, default_specification=DRAFT202012),
            ),
        ]
    )
    return Draft202012Validator(schema, registry=registry)


def validate_envelope(envelope: dict[str, Any], *, catalog_id: str) -> None:
    """使用官方 JSON Schema 校验单条 A2UI 信封消息。"""

    if envelope.get("version") != A2UI_VERSION:
        raise A2UIValidationError(
            f"A2UI 版本必须为 {A2UI_VERSION}",
            issues=[
                ValidationIssue(
                    code="invalid_version",
                    message=f"version 必须为 {A2UI_VERSION}",
                    path="/version",
                )
            ],
        )

    validator = _validator(catalog_id)
    errors = sorted(validator.iter_errors(envelope), key=lambda err: list(err.path))
    if not errors:
        return

    issues: list[ValidationIssue] = []
    for error in errors[:50]:
        issues.append(
            ValidationIssue(
                code="schema_violation",
                message=error.message,
                path=_pointer(error.absolute_path),
            )
        )
    raise A2UIValidationError(
        f"A2UI 消息不符合 schema（catalog={catalog_id}）",
        issues=issues,
    )


def get_component_refs(component: dict[str, Any]) -> list[tuple[str, str]]:
    """返回组件内所有对子组件的引用：``[(component_id, property_path), ...]``。"""

    refs: list[tuple[str, str]] = []

    def add_ref(value: Any, prop: str) -> None:
        if isinstance(value, str) and value:
            refs.append((value, prop))

    children = component.get("children")
    if isinstance(children, list):
        for index, child in enumerate(children):
            add_ref(child, f"children/{index}")
    elif isinstance(children, dict):
        add_ref(children.get("componentId"), "children/componentId")

    for key in ("child", "entryPointChild", "contentChild"):
        add_ref(component.get(key), key)

    for key in ("tabs", "tabItems"):
        tabs = component.get(key)
        if isinstance(tabs, list):
            for index, tab in enumerate(tabs):
                if isinstance(tab, dict):
                    add_ref(tab.get("child"), f"{key}/{index}/child")

    return refs


def validate_components(
    components: list[dict[str, Any]],
    *,
    catalog_id: str,
) -> list[ValidationIssue]:
    """校验组件列表自身的合法性（重复 ID、未知类型、自引用）。"""

    issues: list[ValidationIssue] = []
    seen: set[str] = set()
    known_types = component_names()

    for index, component in enumerate(components):
        component_id = component.get("id")
        component_type = component.get("component")
        base = f"/components/{index}"

        if not isinstance(component_id, str) or not component_id:
            issues.append(
                ValidationIssue(
                    code="invalid_component_id",
                    message="组件 id 必须是非空字符串",
                    path=f"{base}/id",
                )
            )
            continue

        if component_id in seen:
            issues.append(
                ValidationIssue(
                    code="duplicate_component_id",
                    message=f"同一条消息中组件 id 重复：{component_id!r}",
                    path=f"{base}/id",
                )
            )
        seen.add(component_id)

        if not isinstance(component_type, str) or not component_type:
            issues.append(
                ValidationIssue(
                    code="invalid_component_type",
                    message="组件 component 必须是非空字符串",
                    path=f"{base}/component",
                )
            )
        elif catalog_id == BASIC_CATALOG_ID and component_type not in known_types:
            issues.append(
                ValidationIssue(
                    code="unknown_component_type",
                    message=f"基础组件目录中不存在组件类型 {component_type!r}",
                    path=f"{base}/component",
                )
            )

    if issues:
        raise A2UIValidationError("A2UI 组件定义不合法", issues=issues)
    return issues


def validate_surface_graph(
    components: dict[str, dict[str, Any]],
) -> list[ValidationIssue]:
    """校验合并后的 surface 组件图。

    - 必须存在 ``root`` 组件；
    - 不允许循环引用；
    - 悬空的子组件引用只作为 warning 返回，允许渐进式渲染。
    """

    if "root" not in components:
        raise A2UIValidationError(
            "surface 必须包含 id 为 'root' 的根组件",
            issues=[
                ValidationIssue(
                    code="missing_root",
                    message="未找到 id 为 'root' 的组件",
                    path="/components",
                )
            ],
        )

    warnings: list[ValidationIssue] = []
    for component_id, component in components.items():
        for target, prop in get_component_refs(component):
            if target not in components:
                warnings.append(
                    ValidationIssue(
                        code="dangling_component_reference",
                        message=f"组件 {component_id!r} 引用了不存在的子组件 {target!r}",
                        path=f"/components/{component_id}/{prop}",
                    )
                )

    # DFS 检测环
    state: dict[str, int] = {}
    path: list[str] = []

    def visit(node_id: str) -> None:
        marker = state.get(node_id, 0)
        if marker == 1:
            cycle = " -> ".join(path[path.index(node_id) :] + [node_id])
            raise A2UIValidationError(
                "A2UI 组件图存在循环引用",
                issues=[
                    ValidationIssue(
                        code="component_cycle",
                        message=f"检测到循环引用：{cycle}",
                        path=f"/components/{node_id}",
                    )
                ],
            )
        if marker == 2:
            return
        state[node_id] = 1
        path.append(node_id)
        component = components.get(node_id)
        if component is not None:
            for target, _ in get_component_refs(component):
                if target in components:
                    visit(target)
        path.pop()
        state[node_id] = 2

    for component_id in components:
        visit(component_id)

    return warnings
