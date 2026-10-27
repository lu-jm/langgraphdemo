from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver

from app.a2ui.service import A2UIService
from app.agent.graph import build_graph
from app.config import Settings
from app.main import create_app
from tests.helpers import FakeToolChatModel


@dataclass
class AppBundle:
    app: Any
    graph: Any
    service: A2UIService
    model: FakeToolChatModel


@pytest.fixture()
def settings() -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        zhipuai_api_key="test-key",
        zhipuai_model="glm-test",
        log_level="WARNING",
        checkpoint_backend="memory",
        agui_emit_raw_events=False,
    )


@pytest.fixture()
def service() -> A2UIService:
    return A2UIService()


@pytest.fixture()
def bundle_factory(settings: Settings, service: A2UIService):
    def factory(responses: list[AIMessage]) -> AppBundle:
        model = FakeToolChatModel(responses=responses)
        graph = build_graph(
            settings,
            checkpointer=MemorySaver(),
            model=model,
            a2ui_service=service,
        )
        app = create_app(settings, graph=graph, a2ui_service=service)
        return AppBundle(app=app, graph=graph, service=service, model=model)

    return factory


@pytest.fixture()
def bundle(bundle_factory) -> AppBundle:
    return bundle_factory([AIMessage(content="你好，我是测试助手。")])


@pytest.fixture()
def client(bundle: AppBundle):
    with TestClient(bundle.app) as test_client:
        yield test_client
