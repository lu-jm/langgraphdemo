"""A2UI Surface 构建辅助工具。

用 Python 代码声明式地构建邻接表组件树，并生成 createSurface /
updateComponents / updateDataModel 操作序列。
"""

from __future__ import annotations

import copy
from collections.abc import Iterable
from typing import Any

from app.a2ui.constants import A2UI_VERSION, BASIC_CATALOG_ID


def _clean(props: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in props.items() if value is not None}


class SurfaceBuilder:
    """按插入顺序构建 A2UI v0.9 surface。"""

    def __init__(
        self,
        surface_id: str,
        *,
        catalog_id: str = BASIC_CATALOG_ID,
        theme: dict[str, Any] | None = None,
        send_data_model: bool = False,
    ) -> None:
        if not surface_id:
            raise ValueError("surface_id 不能为空")
        self.surface_id = surface_id
        self.catalog_id = catalog_id
        self.theme = theme
        self.send_data_model = send_data_model
        self._components: dict[str, dict[str, Any]] = {}

    # -- 基础操作 ---------------------------------------------------------

    def add(self, component: str, component_id: str, **props: Any) -> SurfaceBuilder:
        if not component_id:
            raise ValueError("component_id 不能为空")
        if component_id in self._components:
            raise ValueError(f"组件 id 重复：{component_id!r}")
        self._components[component_id] = {
            "id": component_id,
            "component": component,
            **_clean(props),
        }
        return self

    def update(self, component: str, component_id: str, **props: Any) -> SurfaceBuilder:
        """覆盖已有组件（用于渐进式更新）。"""

        if component_id not in self._components:
            raise KeyError(f"组件不存在：{component_id!r}")
        self._components[component_id] = {
            "id": component_id,
            "component": component,
            **_clean(props),
        }
        return self

    @property
    def components(self) -> list[dict[str, Any]]:
        return copy.deepcopy(list(self._components.values()))

    # -- 常用组件快捷方法 -------------------------------------------------

    def text(
        self,
        component_id: str,
        text: Any,
        *,
        variant: str = "body",
        **props: Any,
    ) -> SurfaceBuilder:
        return self.add("Text", component_id, text=text, variant=variant, **props)

    def image(
        self,
        component_id: str,
        url: Any,
        *,
        fit: str = "cover",
        variant: str = "mediumFeature",
        **props: Any,
    ) -> SurfaceBuilder:
        return self.add(
            "Image", component_id, url=url, fit=fit, variant=variant, **props
        )

    def icon(self, component_id: str, name: str, **props: Any) -> SurfaceBuilder:
        return self.add("Icon", component_id, name=name, **props)

    def divider(self, component_id: str, *, axis: str = "horizontal") -> SurfaceBuilder:
        return self.add("Divider", component_id, axis=axis)

    def row(
        self,
        component_id: str,
        children: list[str],
        *,
        justify: str = "start",
        align: str = "stretch",
        **props: Any,
    ) -> SurfaceBuilder:
        return self.add(
            "Row",
            component_id,
            children=children,
            justify=justify,
            align=align,
            **props,
        )

    def column(
        self,
        component_id: str,
        children: list[str],
        *,
        justify: str = "start",
        align: str = "stretch",
        **props: Any,
    ) -> SurfaceBuilder:
        return self.add(
            "Column",
            component_id,
            children=children,
            justify=justify,
            align=align,
            **props,
        )

    def list(
        self,
        component_id: str,
        children: list[str] | dict[str, str],
        *,
        direction: str = "vertical",
        align: str = "stretch",
        **props: Any,
    ) -> SurfaceBuilder:
        return self.add(
            "List",
            component_id,
            children=children,
            direction=direction,
            align=align,
            **props,
        )

    def card(self, component_id: str, child: str, **props: Any) -> SurfaceBuilder:
        return self.add("Card", component_id, child=child, **props)

    def text_field(
        self,
        component_id: str,
        label: str,
        *,
        value: Any = None,
        variant: str = "shortText",
        **props: Any,
    ) -> SurfaceBuilder:
        return self.add(
            "TextField",
            component_id,
            label=label,
            value=value,
            variant=variant,
            **props,
        )

    def checkbox(
        self, component_id: str, label: str, *, value: Any = None, **props: Any
    ) -> SurfaceBuilder:
        return self.add("CheckBox", component_id, label=label, value=value, **props)

    def button(
        self,
        component_id: str,
        child: str,
        *,
        variant: str = "primary",
        action: dict[str, Any] | None = None,
        **props: Any,
    ) -> SurfaceBuilder:
        return self.add(
            "Button",
            component_id,
            child=child,
            variant=variant,
            action=action,
            **props,
        )

    def tabs(
        self, component_id: str, tabs: Iterable[dict[str, Any]], **props: Any
    ) -> SurfaceBuilder:
        return self.add("Tabs", component_id, tabs=list(tabs), **props)

    # -- 生成 A2UI 操作 ---------------------------------------------------

    def create_op(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "surfaceId": self.surface_id,
            "catalogId": self.catalog_id,
        }
        if self.theme is not None:
            payload["theme"] = self.theme
        if self.send_data_model:
            payload["sendDataModel"] = True
        return {"version": A2UI_VERSION, "createSurface": payload}

    def components_op(self) -> dict[str, Any]:
        return {
            "version": A2UI_VERSION,
            "updateComponents": {
                "surfaceId": self.surface_id,
                "components": self.components,
            },
        }

    def data_op(
        self, data: Any, *, path: str = "/", delete: bool = False
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"surfaceId": self.surface_id, "path": path}
        if not delete:
            payload["value"] = data
        return {"version": A2UI_VERSION, "updateDataModel": payload}

    def delete_op(self) -> dict[str, Any]:
        return {
            "version": A2UI_VERSION,
            "deleteSurface": {"surfaceId": self.surface_id},
        }

    def build_ops(
        self,
        *,
        intent: str = "create",
        data: Any | None = None,
    ) -> list[dict[str, Any]]:
        """生成可直接下发给前端的操作列表。"""

        ops: list[dict[str, Any]] = []
        if intent != "update":
            ops.append(self.create_op())
        ops.append(self.components_op())
        if data is not None:
            ops.append(self.data_op(data))
        return ops


def demo_surface(
    surface_id: str, *, catalog_id: str = BASIC_CATALOG_ID
) -> list[dict[str, Any]]:
    """构建一个用于联调的最小 A2UI surface（表单 + 按钮）。"""

    builder = SurfaceBuilder(
        surface_id,
        catalog_id=catalog_id,
        theme={"primaryColor": "#2563EB", "agentDisplayName": "LangGraph Agent"},
        send_data_model=True,
    )
    builder.card("root", "content")
    builder.column(
        "content",
        ["title", "subtitle", "divider", "form", "actions"],
    )
    builder.text("title", "A2UI 联调示例", variant="h2")
    builder.text(
        "subtitle",
        "这个界面完全由后端下发的 A2UI JSON 描述，前端使用原生组件渲染。",
        variant="body",
    )
    builder.divider("divider")
    builder.column("form", ["name_field", "subscribe"])
    builder.text_field("name_field", "你的名字", value={"path": "/form/name"})
    builder.checkbox("subscribe", "订阅更新", value={"path": "/form/subscribe"})
    builder.row("actions", ["submit_button"], justify="end")
    builder.text("submit_text", "提交")
    builder.button(
        "submit_button",
        "submit_text",
        variant="primary",
        action={
            "event": {
                "name": "submitDemoForm",
                "context": {
                    "name": {"path": "/form/name"},
                    "subscribe": {"path": "/form/subscribe"},
                },
            }
        },
    )
    return builder.build_ops(data={"form": {"name": "Alice", "subscribe": True}})
