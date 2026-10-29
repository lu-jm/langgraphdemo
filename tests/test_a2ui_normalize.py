"""A2UI 操作归一化测试。"""

from __future__ import annotations

from app.a2ui.normalize import normalize_component, normalize_operation
from app.a2ui.service import A2UIService


def test_image_alt_maps_to_description() -> None:
    component = {
        "id": "cover",
        "component": "Image",
        "url": "https://example.com/cover.png",
        "alt": "产品封面",
    }
    normalized = normalize_component(component)

    assert normalized["description"] == "产品封面"
    assert "alt" not in normalized
    assert component["alt"] == "产品封面"  # 不修改原对象


def test_operation_with_image_alt_is_applied() -> None:
    service = A2UIService()
    operations = [
        {
            "version": "v0.9",
            "createSurface": {
                "surfaceId": "product",
                "catalogId": service.default_catalog_id,
            },
        },
        {
            "version": "v0.9",
            "updateComponents": {
                "surfaceId": "product",
                "components": [
                    {"id": "root", "component": "Column", "children": ["title", "cover"]},
                    {"id": "title", "component": "Text", "text": "机械键盘"},
                    {
                        "id": "cover",
                        "component": "Image",
                        "url": "https://example.com/cover.png",
                        "alt": "产品封面",
                    },
                ],
            },
        },
    ]

    result = service.apply_operations(
        "normalize-thread",
        [normalize_operation(operation) for operation in operations],
    )

    assert result.errors == []
    surface = service.get_surface("normalize-thread", "product")
    assert set(surface.components) == {"root", "title", "cover"}
    assert surface.components["cover"]["description"] == "产品封面"
    assert "alt" not in surface.components["cover"]
