from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.a2ui.builder import SurfaceBuilder, demo_surface
from app.a2ui.constants import BASIC_CATALOG_ID
from app.a2ui.exceptions import A2UIValidationError
from app.a2ui.models import A2UIClientAction, A2UIMessage
from app.a2ui.validation import validate_envelope


def test_parse_create_surface_roundtrip():
    message = A2UIMessage.model_validate(
        {
            "version": "v0.9",
            "createSurface": {
                "surfaceId": "s1",
                "catalogId": BASIC_CATALOG_ID,
                "sendDataModel": True,
                "theme": {"primaryColor": "#2563EB"},
            },
        }
    )
    assert message.kind == "createSurface"
    assert message.surface_id == "s1"
    assert message.to_envelope()["createSurface"]["sendDataModel"] is True


def test_update_data_model_preserves_explicit_null():
    message = A2UIMessage.model_validate(
        {
            "version": "v0.9",
            "updateDataModel": {
                "surfaceId": "s1",
                "path": "/form/name",
                "value": None,
            },
        }
    )
    envelope = message.to_envelope()
    assert "value" in envelope["updateDataModel"]
    assert envelope["updateDataModel"]["value"] is None


def test_update_data_model_can_omit_value_to_delete():
    message = A2UIMessage.model_validate(
        {
            "version": "v0.9",
            "updateDataModel": {"surfaceId": "s1", "path": "/form/name"},
        }
    )
    assert "value" not in message.to_envelope()["updateDataModel"]
    assert message.update_data_model.deletes_value is True


def test_exactly_one_message_type():
    with pytest.raises(ValidationError):
        A2UIMessage.model_validate({"version": "v0.9"})

    with pytest.raises(ValidationError):
        A2UIMessage.model_validate(
            {
                "version": "v0.9",
                "createSurface": {"surfaceId": "a", "catalogId": BASIC_CATALOG_ID},
                "deleteSurface": {"surfaceId": "a"},
            }
        )


def test_component_keeps_catalog_specific_props():
    message = A2UIMessage.model_validate(
        {
            "version": "v0.9",
            "updateComponents": {
                "surfaceId": "s1",
                "components": [
                    {
                        "id": "root",
                        "component": "Column",
                        "children": ["text"],
                        "customProp": {"a": 1},
                    },
                    {"id": "text", "component": "Text", "text": "hi", "variant": "h2"},
                ],
            },
        }
    )
    components = message.update_components.components
    assert components[0].model_extra["customProp"] == {"a": 1}

    # 基础目录不允许未声明的属性，自定义目录则允许随组件携带扩展属性。
    with pytest.raises(A2UIValidationError):
        validate_envelope(message.to_envelope(), catalog_id=BASIC_CATALOG_ID)
    validate_envelope(
        message.to_envelope(),
        catalog_id="https://example.com/catalogs/custom/catalog.json",
    )


def test_client_action():
    action = A2UIClientAction.model_validate(
        {
            "name": "submit",
            "surfaceId": "s1",
            "sourceComponentId": "button",
            "timestamp": datetime.now(UTC).isoformat(),
            "context": {"name": "Alice"},
        }
    )
    assert action.surface_id == "s1"
    dumped = action.model_dump(mode="json", by_alias=True)
    assert dumped["sourceComponentId"] == "button"


def test_builder_generates_valid_demo_surface():
    operations = demo_surface("demo-1")
    assert len(operations) == 3
    for operation in operations:
        validate_envelope(operation, catalog_id=BASIC_CATALOG_ID)


def test_builder_rejects_duplicate_id():
    builder = SurfaceBuilder("s1")
    builder.text("root", "hello")
    with pytest.raises(ValueError):
        builder.text("root", "again")


def test_schema_rejects_unknown_component():
    operations = demo_surface("demo-2")
    operations[1]["updateComponents"]["components"][0]["component"] = "Unknown"
    with pytest.raises(Exception) as exc_info:
        validate_envelope(operations[1], catalog_id=BASIC_CATALOG_ID)
    assert exc_info.value.code == "a2ui_validation_failed"
