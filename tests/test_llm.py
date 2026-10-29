"""模型工厂与思考模式配置测试。"""

from __future__ import annotations

from app.agent.llm import build_chat_model
from app.config import Settings


def _settings(**overrides) -> Settings:
    values = {
        "_env_file": None,
        "llm_provider": "openai",
        "openai_api_key": "test-key",
        "openai_model": "deepseek-flash",
    }
    values.update(overrides)
    return Settings(**values)


def test_auto_disables_thinking_for_deepseek() -> None:
    settings = _settings(openai_base_url="https://api.deepseek.com")
    assert settings.openai_extra_body == {"thinking": {"type": "disabled"}}


def test_auto_omits_thinking_for_other_providers() -> None:
    settings = _settings(openai_base_url="https://api.openai.com/v1")
    assert settings.openai_extra_body is None


def test_explicit_thinking_mode() -> None:
    settings = _settings(
        openai_base_url="https://api.deepseek.com",
        openai_thinking_mode="enabled",
    )
    assert settings.openai_extra_body == {"thinking": {"type": "enabled"}}


def test_chat_model_receives_extra_body() -> None:
    settings = _settings(openai_base_url="https://api.deepseek.com")
    model = build_chat_model(settings)
    assert model.extra_body == {"thinking": {"type": "disabled"}}
