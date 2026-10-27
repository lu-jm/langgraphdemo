"""A2UI v0.9 协议 Pydantic 模型。

对应官方 schema:
https://github.com/a2ui-project/a2ui/tree/main/specification/v0_9/json
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.a2ui.constants import A2UI_VERSION

JSON = dict[str, Any]


class _AliasedModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
        str_strip_whitespace=False,
    )


class DataBinding(BaseModel):
    """数据模型绑定，使用 JSON Pointer（RFC 6901）。"""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    path: str


class FunctionCall(BaseModel):
    """客户端函数调用。"""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    call: str
    args: JSON | None = None
    return_type: str | None = Field(default=None, alias="returnType")


class Component(BaseModel):
    """A2UI 组件。

    A2UI v0.9 的组件是扁平结构：``{"id": "root", "component": "Column", ...}``。
    组件属性由具体 catalog 定义，因此这里允许额外字段，并通过官方 JSON Schema
    做严格校验。
    """

    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow",
        validate_assignment=True,
    )

    id: str = Field(min_length=1)
    component: str = Field(min_length=1)

    @property
    def props(self) -> JSON:
        """返回除 id/component 外的组件属性。"""

        return {
            key: value
            for key, value in self.model_dump(by_alias=True, exclude_none=True).items()
            if key not in {"id", "component"}
        }


class CreateSurfacePayload(_AliasedModel):
    surface_id: str = Field(alias="surfaceId", min_length=1)
    catalog_id: str = Field(alias="catalogId", min_length=1)
    theme: JSON | None = None
    send_data_model: bool | None = Field(default=None, alias="sendDataModel")


class UpdateComponentsPayload(_AliasedModel):
    surface_id: str = Field(alias="surfaceId", min_length=1)
    components: list[Component] = Field(min_length=1)


class UpdateDataModelPayload(_AliasedModel):
    surface_id: str = Field(alias="surfaceId", min_length=1)
    path: str | None = None
    # None 是合法的 JSON 值，因此通过 model_fields_set 判断字段是否省略。
    value: Any = None

    @property
    def deletes_value(self) -> bool:
        return "value" not in self.model_fields_set


class DeleteSurfacePayload(_AliasedModel):
    surface_id: str = Field(alias="surfaceId", min_length=1)


class A2UIMessage(_AliasedModel):
    """A2UI 服务端 -> 客户端信封消息，四个 key 中恰好出现一个。"""

    version: Literal["v0.9"] = A2UI_VERSION
    create_surface: CreateSurfacePayload | None = Field(
        default=None, alias="createSurface"
    )
    update_components: UpdateComponentsPayload | None = Field(
        default=None, alias="updateComponents"
    )
    update_data_model: UpdateDataModelPayload | None = Field(
        default=None, alias="updateDataModel"
    )
    delete_surface: DeleteSurfacePayload | None = Field(
        default=None, alias="deleteSurface"
    )

    @model_validator(mode="after")
    def _exactly_one_message(self) -> A2UIMessage:
        present = [
            name
            for name, value in (
                ("createSurface", self.create_surface),
                ("updateComponents", self.update_components),
                ("updateDataModel", self.update_data_model),
                ("deleteSurface", self.delete_surface),
            )
            if value is not None
        ]
        if len(present) != 1:
            raise ValueError(
                "A2UI 消息必须且只能包含 createSurface、updateComponents、"
                f"updateDataModel、deleteSurface 之一，当前包含 {present or '无'}"
            )
        return self

    @property
    def kind(self) -> str:
        for name in (
            "createSurface",
            "updateComponents",
            "updateDataModel",
            "deleteSurface",
        ):
            if getattr(self, _snake(name)) is not None:
                return name
        raise RuntimeError("unreachable")

    @property
    def surface_id(self) -> str:
        payload = self._payload()
        return payload.surface_id  # type: ignore[union-attr]

    def _payload(self):
        return (
            self.create_surface
            or self.update_components
            or self.update_data_model
            or self.delete_surface
        )

    def to_envelope(self) -> JSON:
        """序列化为符合 A2UI 协议的 camelCase 字典。"""

        envelope: JSON = {"version": self.version}
        if self.create_surface is not None:
            envelope["createSurface"] = self.create_surface.model_dump(
                by_alias=True, exclude_none=True
            )
        elif self.update_components is not None:
            envelope["updateComponents"] = self.update_components.model_dump(
                by_alias=True, exclude_none=True
            )
        elif self.update_data_model is not None:
            payload = self.update_data_model.model_dump(
                by_alias=True, exclude_none=True
            )
            # 显式传入 value=null 时不能被 exclude_none 丢掉。
            if not self.update_data_model.deletes_value:
                payload["value"] = self.update_data_model.value
            envelope["updateDataModel"] = payload
        elif self.delete_surface is not None:
            envelope["deleteSurface"] = self.delete_surface.model_dump(
                by_alias=True, exclude_none=True
            )
        return envelope

    @classmethod
    def from_envelope(cls, envelope: JSON) -> A2UIMessage:
        return cls.model_validate(envelope)


def _snake(name: str) -> str:
    return "".join(f"_{char.lower()}" if char.isupper() else char for char in name)


class A2UIClientAction(BaseModel):
    """客户端 -> 服务端的 A2UI action 消息。"""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    name: str = Field(min_length=1)
    surface_id: str = Field(alias="surfaceId", min_length=1)
    source_component_id: str = Field(alias="sourceComponentId", min_length=1)
    timestamp: datetime
    context: JSON = Field(default_factory=dict)


class A2UIError(BaseModel):
    """客户端 -> 服务端的错误消息。"""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    code: str
    message: str
    surface_id: str = Field(alias="surfaceId")
