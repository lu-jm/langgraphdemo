from __future__ import annotations

from app.a2ui.constants import BASIC_CATALOG_ID
from app.a2ui.toolkit import parse_tool_content
from app.a2ui.validation import validate_envelope
from app.agent.tools.a2ui_tools import build_agent_tools, render_calculation_card
from app.agent.tools.math import add, multiply
from app.config import Settings
from tests.conftest import FakeToolChatModel


def test_math_tools():
    assert add.invoke({"first_number": 1, "second_number": 1}) == 2
    assert multiply.invoke({"first_number": 3, "second_number": 4}) == 12


def test_calculation_card_tool_returns_valid_a2ui():
    content = render_calculation_card.invoke(
        {"expression": "1 + 1", "result": "2", "notes": "测试"}
    )
    operations = parse_tool_content(content)
    assert len(operations) == 3
    for operation in operations:
        validate_envelope(operation, catalog_id=BASIC_CATALOG_ID)
    assert operations[0]["createSurface"]["surfaceId"].startswith("calc-")


def test_parse_tool_content_handles_text_blocks():
    assert parse_tool_content(
        [{"type": "text", "text": '{"a2ui_operations": [{"x": 1}]}'}]
    ) == [{"x": 1}]
    assert parse_tool_content("plain text") == []


def test_build_agent_tools_includes_dynamic_a2ui():
    settings = Settings(
        _env_file=None,
        environment="test",
        zhipuai_api_key="test",
        enable_dynamic_a2ui=True,
        log_level="WARNING",
    )
    model = FakeToolChatModel(responses=[])
    names = {tool.name for tool in build_agent_tools(settings, model)}
    assert {"add", "multiply", "render_calculation_card", "generate_a2ui"} <= names


def test_dynamic_a2ui_can_be_disabled():
    settings = Settings(
        _env_file=None,
        environment="test",
        zhipuai_api_key="test",
        enable_dynamic_a2ui=False,
        log_level="WARNING",
    )
    model = FakeToolChatModel(responses=[])
    names = {tool.name for tool in build_agent_tools(settings, model)}
    assert "generate_a2ui" not in names
