from __future__ import annotations

import pytest

from app.a2ui.builder import demo_surface
from app.a2ui.constants import BASIC_CATALOG_ID
from app.a2ui.exceptions import (
    A2UIValidationError,
    SurfaceAlreadyExistsError,
    SurfaceNotFoundError,
)
from app.a2ui.models import A2UIClientAction, A2UIMessage
from app.a2ui.service import A2UIService
from app.a2ui.store import SurfaceStore
from app.a2ui.validation import validate_envelope


def test_apply_demo_operations(service: A2UIService):
    result = service.apply_operations("t1", demo_surface("demo"))
    assert result.errors == []
    surface = service.get_surface("t1", "demo")
    assert "root" in surface.components
    assert surface.data_model["form"]["name"] == "Alice"


def test_update_components_is_incremental(service: A2UIService):
    service.apply_operations("t1", demo_surface("demo"))
    message = A2UIMessage.model_validate(
        {
            "version": "v0.9",
            "updateComponents": {
                "surfaceId": "demo",
                "components": [
                    {
                        "id": "title",
                        "component": "Text",
                        "text": "新标题",
                        "variant": "h1",
                    }
                ],
            },
        }
    )
    surface, warnings = service.apply_message("t1", message)
    assert warnings == []
    assert surface.components["title"]["text"] == "新标题"
    assert surface.components["root"]["component"] == "Card"


def test_update_and_delete_data_model(service: A2UIService):
    service.apply_operations("t1", demo_surface("demo"))
    update = A2UIMessage.model_validate(
        {
            "version": "v0.9",
            "updateDataModel": {
                "surfaceId": "demo",
                "path": "/form/name",
                "value": "Bob",
            },
        }
    )
    service.apply_message("t1", update)
    assert service.get_surface("t1", "demo").data_model["form"]["name"] == "Bob"

    delete_key = A2UIMessage.model_validate(
        {
            "version": "v0.9",
            "updateDataModel": {"surfaceId": "demo", "path": "/form/name"},
        }
    )
    service.apply_message("t1", delete_key)
    assert "name" not in service.get_surface("t1", "demo").data_model["form"]


def test_strict_duplicate_create_raises(service: A2UIService):
    service.apply_operations("t1", demo_surface("demo"))
    duplicate = A2UIMessage.model_validate(
        {
            "version": "v0.9",
            "createSurface": {"surfaceId": "demo", "catalogId": BASIC_CATALOG_ID},
        }
    )
    with pytest.raises(SurfaceAlreadyExistsError):
        service.apply_message("t1", duplicate, strict=True)


def test_non_strict_duplicate_create_resets_surface(service: A2UIService):
    service.apply_operations("t1", demo_surface("demo"))
    service.apply_operations("t1", demo_surface("demo"))
    assert service.get_surface("t1", "demo").data_model["form"]["name"] == "Alice"


def test_delete_missing_surface_is_noop(service: A2UIService):
    message = A2UIMessage.model_validate(
        {
            "version": "v0.9",
            "deleteSurface": {"surfaceId": "missing"},
        }
    )
    surface, warnings = service.apply_message("t1", message)
    assert surface is None
    assert warnings == []
    assert service.list_surfaces("t1") == []


def test_missing_surface_raises(service: A2UIService):
    message = A2UIMessage.model_validate(
        {
            "version": "v0.9",
            "updateDataModel": {"surfaceId": "nope", "path": "/a", "value": 1},
        }
    )
    with pytest.raises(SurfaceNotFoundError):
        service.apply_message("t1", message)


def test_cycle_detection(service: A2UIService):
    operations = [
        {
            "version": "v0.9",
            "createSurface": {"surfaceId": "cycle", "catalogId": BASIC_CATALOG_ID},
        },
        {
            "version": "v0.9",
            "updateComponents": {
                "surfaceId": "cycle",
                "components": [
                    {"id": "root", "component": "Row", "children": ["a"]},
                    {"id": "a", "component": "Row", "children": ["root"]},
                ],
            },
        },
    ]
    result = service.apply_operations("t1", operations)
    assert result.errors
    assert result.errors[0]["code"] == "a2ui_validation_failed"


def test_dangling_reference_is_warning(service: A2UIService):
    result = service.apply_operations(
        "t1",
        [
            {
                "version": "v0.9",
                "createSurface": {
                    "surfaceId": "dangling",
                    "catalogId": BASIC_CATALOG_ID,
                },
            },
            {
                "version": "v0.9",
                "updateComponents": {
                    "surfaceId": "dangling",
                    "components": [
                        {"id": "root", "component": "Column", "children": ["missing"]}
                    ],
                },
            },
        ],
    )
    assert result.errors == []
    assert any(
        warning.code == "dangling_component_reference" for warning in result.warnings
    )


def test_apply_operations_collects_errors(service: A2UIService):
    result = service.apply_operations(
        "t1",
        [
            {
                "version": "v0.9",
                "updateComponents": {"surfaceId": "x", "components": []},
            },
        ],
    )
    assert result.errors
    assert result.errors[0]["code"] in {
        "a2ui_validation_failed",
        "surface_not_found",
    }


def test_action_recording(service: A2UIService):
    service.apply_operations("t1", demo_surface("demo"))
    action = A2UIClientAction.model_validate(
        {
            "name": "submitDemoForm",
            "surfaceId": "demo",
            "sourceComponentId": "submit_button",
            "timestamp": "2026-10-27T00:00:00Z",
            "context": {"name": "Alice"},
        }
    )
    recorded = service.record_action("t1", action)
    assert recorded["name"] == "submitDemoForm"
    assert service.list_actions("t1")[0]["surfaceId"] == "demo"


def test_store_is_thread_isolated():
    store = SurfaceStore(max_surfaces_per_thread=2)
    service = A2UIService(store=store)
    service.apply_operations("a", demo_surface("one"))
    service.apply_operations("b", demo_surface("two"))
    assert service.store.surface_count("a") == 1
    assert service.store.surface_count("b") == 1
    assert service.list_surfaces("a")[0].surface_id == "one"


def test_invalid_data_model_path(service: A2UIService):
    service.apply_operations("t1", demo_surface("demo"))
    message = A2UIMessage.model_validate(
        {
            "version": "v0.9",
            "updateDataModel": {
                "surfaceId": "demo",
                "path": "items/not-a-number",
                "value": 1,
            },
        }
    )
    with pytest.raises(A2UIValidationError):
        service.apply_message("t1", message)


def test_validate_envelope_rejects_wrong_version():
    with pytest.raises(A2UIValidationError):
        validate_envelope(
            {
                "version": "v0.8",
                "createSurface": {"surfaceId": "s", "catalogId": BASIC_CATALOG_ID},
            },
            catalog_id=BASIC_CATALOG_ID,
        )
