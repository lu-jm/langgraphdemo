"""系统接口模型。"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from app.schemas.base import APIModel


class ServiceInfo(APIModel):
    name: str
    version: str
    environment: str
    docs: str
    endpoints: dict[str, str] = Field(default_factory=dict)


class HealthResponse(APIModel):
    status: str = "ok"
    version: str
    environment: str
    model: dict[str, Any] = Field(default_factory=dict)
    a2ui: dict[str, Any] = Field(default_factory=dict)
    checkpoint: dict[str, Any] = Field(default_factory=dict)
