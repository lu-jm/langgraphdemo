"""应用配置。

所有敏感信息（模型 API Key）都通过环境变量或 ``.env`` 注入，代码中不再硬编码。
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.a2ui.constants import BASIC_CATALOG_ID


class Settings(BaseSettings):
    """从环境变量读取的后端配置。

    环境变量名与字段名一致（大小写不敏感），例如 ``ZHIPUAI_API_KEY``、
    ``CHECKPOINT_BACKEND``。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- 应用信息 ---------------------------------------------------------
    app_name: str = "LangGraph A2UI Agent"
    app_version: str = "0.1.0"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    # CORS，多个来源用逗号分隔；"*" 表示允许全部。
    cors_origins: str = "*"

    # --- LLM --------------------------------------------------------------
    llm_provider: Literal["zhipu", "openai"] = "openai"
    zhipuai_api_key: str | None = None
    zhipuai_model: str = "glm-4.7"
    zhipuai_temperature: float = 0.3

    openai_api_key: str | None = None
    openai_model: str = "deepseek-flash"
    openai_base_url: str | None = "https://api.deepseek.com"
    openai_temperature: float = 0.3
    # DeepSeek 思考模式开关：auto / enabled / disabled。
    # auto：DeepSeek 域名下自动关闭，其他兼容接口不发送该字段；
    # DeepSeek 思考模式不支持强制 tool_choice（动态 A2UI 子 Agent 会用到），
    # 因此默认建议 disabled。
    openai_thinking_mode: Literal["auto", "enabled", "disabled"] = "auto"

    # --- Agent ------------------------------------------------------------
    agent_recursion_limit: int = 30
    agent_parallel_tool_calls: bool = False
    enable_dynamic_a2ui: bool = True

    # 是否在 AG-UI SSE 中附带 LangGraph 原始事件（体积较大，默认关闭）。
    agui_emit_raw_events: bool = False
    agui_emit_subagent_events: bool = False

    # --- A2UI -------------------------------------------------------------
    a2ui_catalog_id: str = BASIC_CATALOG_ID
    a2ui_max_surfaces_per_thread: int = 50
    a2ui_max_actions_per_thread: int = 100

    # --- 会话持久化 -------------------------------------------------------
    checkpoint_backend: Literal["memory", "sqlite"] = "memory"
    checkpoint_sqlite_path: str = "data/checkpoints.sqlite"

    # --- 文档 -------------------------------------------------------------
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"
    openapi_url: str = "/openapi.json"

    @field_validator("log_level")
    @classmethod
    def _normalize_log_level(cls, value: str) -> str:
        return value.upper()

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def model_api_key(self) -> str | None:
        if self.llm_provider == "openai":
            return self.openai_api_key
        return self.zhipuai_api_key

    @property
    def model_configured(self) -> bool:
        return bool(self.model_api_key)

    @property
    def openai_extra_body(self) -> dict[str, Any] | None:
        """OpenAI 兼容接口的额外请求体。

        DeepSeek 的思考模式默认开启，且不支持强制 ``tool_choice``；
        动态 A2UI 子 Agent 需要强制工具调用，因此在 DeepSeek 域名下自动关闭。
        其他 OpenAI 兼容服务不发送该字段，避免不识别 ``thinking`` 参数。
        """

        mode = self.openai_thinking_mode
        if mode == "auto":
            base_url = (self.openai_base_url or "").lower()
            if "deepseek" not in base_url:
                return None
            mode = "disabled"
        return {"thinking": {"type": mode}}

    @property
    def active_model_name(self) -> str:
        if self.llm_provider == "openai":
            return self.openai_model
        return self.zhipuai_model

    @property
    def checkpoint_config_error(self) -> str | None:
        if self.checkpoint_backend == "sqlite" and not self.checkpoint_sqlite_path:
            return "CHECKPOINT_BACKEND=sqlite 时必须配置 CHECKPOINT_SQLITE_PATH"
        return None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """返回进程级配置单例。"""

    return Settings()
