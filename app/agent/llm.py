"""大模型工厂。

默认使用智谱 GLM（项目原有方案），也支持 OpenAI 兼容接口。
"""

from __future__ import annotations

import logging

from langchain_core.language_models import BaseChatModel

from app.config import Settings
from app.errors import ModelNotConfiguredError

logger = logging.getLogger(__name__)


def build_chat_model(settings: Settings) -> BaseChatModel:
    """按配置创建 ChatModel；缺少 Key 时抛出可读错误。"""

    if not settings.model_configured:
        raise ModelNotConfiguredError(
            f"未配置 {settings.llm_provider.upper()} 的 API Key，无法创建模型。"
        )

    if settings.llm_provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            temperature=settings.openai_temperature,
        )

    from langchain_community.chat_models import ChatZhipuAI

    return ChatZhipuAI(
        model=settings.zhipuai_model,
        zhipuai_api_key=settings.zhipuai_api_key,
        temperature=settings.zhipuai_temperature,
    )


def try_build_chat_model(settings: Settings) -> BaseChatModel | None:
    """启动阶段使用：没有 Key 时返回 None，而不是让应用启动失败。"""

    try:
        return build_chat_model(settings)
    except ModelNotConfiguredError:
        logger.warning(
            "未配置模型 API Key（provider=%s），/api/chat 将返回 503；"
            "A2UI REST 接口仍可使用。",
            settings.llm_provider,
        )
        return None
