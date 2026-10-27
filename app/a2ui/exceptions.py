"""A2UI 领域异常。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.errors import AppError, ConflictError, NotFoundError


@dataclass(slots=True)
class ValidationIssue:
    code: str
    message: str
    path: str = "/"

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message, "path": self.path}


class A2UIValidationError(AppError):
    status_code = 422
    code = "a2ui_validation_failed"

    def __init__(self, message: str, *, issues: list[ValidationIssue] | None = None):
        self.issues = issues or []
        super().__init__(
            message,
            details=[issue.to_dict() for issue in self.issues],
        )


class SurfaceNotFoundError(NotFoundError):
    code = "surface_not_found"

    def __init__(self, surface_id: str, thread_id: str) -> None:
        super().__init__(
            f"线程 {thread_id!r} 中不存在 A2UI surface {surface_id!r}",
            details={"surfaceId": surface_id, "threadId": thread_id},
        )


class SurfaceAlreadyExistsError(ConflictError):
    code = "surface_already_exists"

    def __init__(self, surface_id: str, thread_id: str) -> None:
        super().__init__(
            f"线程 {thread_id!r} 中已存在 A2UI surface {surface_id!r}，"
            "请先 deleteSurface 或使用 updateComponents",
            details={"surfaceId": surface_id, "threadId": thread_id},
        )


class InvalidActionError(AppError):
    status_code = 400
    code = "invalid_a2ui_action"

    def __init__(self, message: str, *, details: Any | None = None) -> None:
        super().__init__(message, details=details)
