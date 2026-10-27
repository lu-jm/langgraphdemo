"""A2UI 业务服务：校验、应用消息、维护 surface 状态。"""

from __future__ import annotations

import logging
from collections import OrderedDict
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from app.a2ui.constants import BASIC_CATALOG_ID
from app.a2ui.exceptions import (
    A2UIValidationError,
    SurfaceAlreadyExistsError,
    SurfaceNotFoundError,
    ValidationIssue,
)
from app.a2ui.json_pointer import JsonPointerError, remove_value, set_value
from app.a2ui.models import A2UIClientAction, A2UIMessage
from app.a2ui.store import Surface, SurfaceStore, utcnow
from app.a2ui.validation import (
    validate_components,
    validate_envelope,
    validate_surface_graph,
)
from app.errors import AppError

logger = logging.getLogger(__name__)


def _pydantic_pointer(location: Iterable[Any]) -> str:
    segments = [str(part) for part in location]
    if not segments:
        return "/"
    return "/" + "/".join(
        segment.replace("~", "~0").replace("/", "~1") for segment in segments
    )


@dataclass(slots=True)
class ApplyResult:
    surfaces: dict[str, Surface] = field(default_factory=dict)
    warnings: list[ValidationIssue] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "surfaces": [surface.to_dict() for surface in self.surfaces.values()],
            "warnings": [warning.to_dict() for warning in self.warnings],
            "errors": self.errors,
        }


class A2UIService:
    def __init__(
        self,
        *,
        default_catalog_id: str = BASIC_CATALOG_ID,
        store: SurfaceStore | None = None,
    ) -> None:
        self.default_catalog_id = default_catalog_id
        self.store = store or SurfaceStore()

    # -- 查询 -------------------------------------------------------------

    def get_surface(self, thread_id: str, surface_id: str) -> Surface:
        surface = self.store.get(thread_id, surface_id)
        if surface is None:
            raise SurfaceNotFoundError(surface_id, thread_id)
        return surface

    def list_surfaces(self, thread_id: str) -> list[Surface]:
        return self.store.list(thread_id)

    def delete_surface(self, thread_id: str, surface_id: str) -> None:
        self.store.delete(thread_id, surface_id)

    def clear_thread(self, thread_id: str) -> None:
        self.store.clear_thread(thread_id)

    # -- 单条消息 ---------------------------------------------------------

    def apply_message(
        self,
        thread_id: str,
        message: A2UIMessage,
        *,
        strict: bool = True,
    ) -> tuple[Surface | None, list[ValidationIssue]]:
        envelope = message.to_envelope()
        payload = message._payload()
        assert payload is not None  # model validator 保证

        existing = self.store.get(thread_id, payload.surface_id)
        catalog_id = (
            message.create_surface.catalog_id
            if message.create_surface is not None
            else (existing.catalog_id if existing else self.default_catalog_id)
        )

        # 1. 官方 JSON Schema 校验
        validate_envelope(envelope, catalog_id=catalog_id)

        # 2. 分发
        warnings: list[ValidationIssue] = []
        if message.create_surface is not None:
            surface = self._create(thread_id, message.create_surface, existing, strict)
        elif message.update_components is not None:
            if existing is None:
                raise SurfaceNotFoundError(payload.surface_id, thread_id)
            surface, warnings = self._update_components(
                existing, message.update_components
            )
        elif message.update_data_model is not None:
            if existing is None:
                raise SurfaceNotFoundError(payload.surface_id, thread_id)
            surface = self._update_data_model(existing, message.update_data_model)
        else:
            if existing is None:
                # 规范规定删除不存在的 surface 是安全的 no-op。
                return None, warnings
            self.store.delete(thread_id, payload.surface_id)
            return existing, warnings

        return surface, warnings

    def _create(
        self, thread_id, payload, existing: Surface | None, strict: bool
    ) -> Surface:
        if existing is not None:
            if strict:
                raise SurfaceAlreadyExistsError(payload.surface_id, thread_id)
            logger.warning(
                "surface %r 已存在，工具重复执行 createSurface，将重置该 surface",
                payload.surface_id,
            )
            existing.catalog_id = payload.catalog_id
            existing.theme = payload.theme
            existing.send_data_model = bool(payload.send_data_model)
            existing.components = OrderedDict()
            existing.data_model = {}
            existing.touch()
            self.store.replace(thread_id, existing.surface_id, existing)
            return existing

        surface = Surface(
            thread_id=thread_id,
            surface_id=payload.surface_id,
            catalog_id=payload.catalog_id,
            theme=payload.theme,
            send_data_model=bool(payload.send_data_model),
        )
        self.store.create(surface)
        return surface

    def _update_components(
        self, surface: Surface, payload
    ) -> tuple[Surface, list[ValidationIssue]]:
        components = [
            component.model_dump(by_alias=True, exclude_none=True)
            for component in payload.components
        ]
        validate_components(components, catalog_id=surface.catalog_id)

        merged = OrderedDict(surface.components)
        for component in components:
            merged[component["id"]] = component

        warnings = validate_surface_graph(merged)
        surface.components = merged
        surface.touch()
        self.store.replace(surface.thread_id, surface.surface_id, surface)
        return surface, warnings

    def _update_data_model(self, surface: Surface, payload) -> Surface:
        path = payload.path if payload.path is not None else "/"
        try:
            if payload.deletes_value:
                surface.data_model = remove_value(surface.data_model, path)
            else:
                surface.data_model = set_value(surface.data_model, path, payload.value)
        except JsonPointerError as exc:
            raise A2UIValidationError(
                f"非法的 updateDataModel path：{path!r}",
                issues=[
                    ValidationIssue(
                        code="invalid_data_model_path",
                        message=str(exc),
                        path="/updateDataModel/path",
                    )
                ],
            ) from exc
        surface.touch()
        self.store.replace(surface.thread_id, surface.surface_id, surface)
        return surface

    # -- 批量/操作列表 ----------------------------------------------------

    def apply_many(
        self,
        thread_id: str,
        messages: Iterable[A2UIMessage],
        *,
        strict: bool = True,
    ) -> ApplyResult:
        message_list = list(messages)
        result = ApplyResult()

        with self.store.transaction(thread_id):
            for message in message_list:
                surface, warnings = self.apply_message(
                    thread_id, message, strict=strict
                )
                if surface is not None:
                    result.surfaces[surface.surface_id] = surface
                result.warnings.extend(warnings)
        return result

    def apply_operations(
        self,
        thread_id: str,
        operations: Iterable[dict[str, Any]],
        *,
        strict: bool = False,
    ) -> ApplyResult:
        """应用工具返回的 a2ui_operations。

        默认非严格模式：允许 createSurface 覆盖已有 surface，并把单条操作的
        错误收集到 ``errors``，避免一次 UI 生成失败打断整个 Agent 运行。
        """

        result = ApplyResult()
        for operation in operations:
            try:
                message = A2UIMessage.from_envelope(operation)
                surface, warnings = self.apply_message(
                    thread_id, message, strict=strict
                )
                if surface is not None:
                    result.surfaces[surface.surface_id] = surface
                result.warnings.extend(warnings)
            except AppError as exc:
                result.errors.append(
                    {
                        "code": exc.code,
                        "message": exc.message,
                        "details": exc.details,
                        "operation": operation,
                    }
                )
                logger.warning("应用 A2UI 操作失败：%s", exc.message)
            except PydanticValidationError as exc:
                issues = [
                    {
                        "code": "schema_violation",
                        "message": error["msg"],
                        "path": _pydantic_pointer(error.get("loc", ())),
                    }
                    for error in exc.errors()[:20]
                ]
                result.errors.append(
                    {
                        "code": "a2ui_validation_failed",
                        "message": "A2UI 操作格式不合法",
                        "details": issues,
                        "operation": operation,
                    }
                )
                logger.warning("A2UI 操作格式不合法：%s", exc)
            except Exception as exc:  # pragma: no cover - 防御性
                result.errors.append(
                    {
                        "code": "a2ui_apply_failed",
                        "message": str(exc),
                        "operation": operation,
                    }
                )
                logger.exception("应用 A2UI 操作出现未预期错误")
        return result

    # -- 客户端 action ----------------------------------------------------

    def record_action(self, thread_id: str, action: A2UIClientAction) -> dict[str, Any]:
        # 不存在时抛出 SurfaceNotFoundError，避免记录指向幽灵 surface 的 action。
        self.get_surface(thread_id, action.surface_id)

        payload = action.model_dump(mode="json", by_alias=True)
        payload["receivedAt"] = utcnow().isoformat()
        payload["threadId"] = thread_id
        self.store.record_action(thread_id, payload)
        return payload

    def list_actions(self, thread_id: str) -> list[dict[str, Any]]:
        return self.store.list_actions(thread_id)

    # -- 统计 -------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        return {
            "threadCount": len(self.store.thread_ids()),
            "surfaceCount": self.store.surface_count(),
        }
