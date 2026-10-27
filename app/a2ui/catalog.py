"""A2UI Basic Catalog 与官方 JSON Schema 加载。

Schema 文件来自 a2ui-project/a2ui 仓库的 ``specification/v0_9``，随项目一起
分发，便于离线校验和向前端暴露组件目录。
"""

from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.a2ui.constants import BASIC_CATALOG_ID

SPEC_DIR = Path(__file__).resolve().parent / "spec" / "v0_9"
SERVER_SCHEMA_PATH = SPEC_DIR / "server_to_client.json"
CLIENT_SCHEMA_PATH = SPEC_DIR / "client_to_server.json"
COMMON_TYPES_PATH = SPEC_DIR / "common_types.json"
BASIC_CATALOG_PATH = SPEC_DIR / "catalogs" / "basic" / "catalog.json"


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def load_server_schema() -> dict[str, Any]:
    return _read_json(SERVER_SCHEMA_PATH)


@lru_cache(maxsize=1)
def load_client_schema() -> dict[str, Any]:
    return _read_json(CLIENT_SCHEMA_PATH)


@lru_cache(maxsize=1)
def load_common_types() -> dict[str, Any]:
    return _read_json(COMMON_TYPES_PATH)


@lru_cache(maxsize=1)
def load_basic_catalog() -> dict[str, Any]:
    return _read_json(BASIC_CATALOG_PATH)


def get_catalog_for_client() -> dict[str, Any]:
    """返回可直接下发给前端/模型的基础组件目录。"""

    catalog = copy.deepcopy(load_basic_catalog())
    catalog.setdefault("catalogId", BASIC_CATALOG_ID)
    return catalog


@lru_cache(maxsize=1)
def component_names() -> frozenset[str]:
    return frozenset(load_basic_catalog().get("components", {}).keys())


@lru_cache(maxsize=1)
def function_names() -> frozenset[str]:
    return frozenset(load_basic_catalog().get("functions", {}).keys())


def component_summary() -> list[dict[str, Any]]:
    """生成简明的组件清单，便于文档与调试接口展示。"""

    catalog = load_basic_catalog()
    result: list[dict[str, Any]] = []
    for name, schema in catalog.get("components", {}).items():
        required: set[str] = set()
        properties: set[str] = set()
        for part in schema.get("allOf", []):
            if not isinstance(part, dict):
                continue
            required.update(part.get("required", []))
            properties.update(part.get("properties", {}).keys())
        result.append(
            {
                "name": name,
                "description": schema.get("description", ""),
                "required": sorted(required - {"component"}),
                "properties": sorted(properties - {"component"}),
            }
        )
    return result


def catalog_id() -> str:
    return load_basic_catalog().get("catalogId", BASIC_CATALOG_ID)
