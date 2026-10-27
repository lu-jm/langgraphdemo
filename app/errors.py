"""统一的业务异常定义。"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """所有可预期业务异常的基类。"""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(
        self,
        message: str,
        *,
        details: Any | None = None,
        status_code: int | None = None,
        code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code


class ModelNotConfiguredError(AppError):
    status_code = 503
    code = "model_not_configured"

    def __init__(self, message: str = "尚未配置大模型 API Key，无法执行对话。") -> None:
        super().__init__(
            message,
            details=(
                "请设置 ZHIPUAI_API_KEY（默认）或 OPENAI_API_KEY，参考 .env.example。"
            ),
        )


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class ValidationFailedError(AppError):
    status_code = 422
    code = "validation_failed"

    def __init__(self, message: str, *, details: Any | None = None) -> None:
        super().__init__(message, details=details)


class UpstreamError(AppError):
    status_code = 502
    code = "upstream_error"
