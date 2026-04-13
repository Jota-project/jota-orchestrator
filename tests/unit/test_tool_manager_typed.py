# tests/unit/test_tool_manager_typed.py
import pytest
from src.core.tool_manager import ToolManager
from src.services.providers.types import ToolSchema


def test_get_typed_tool_schemas_returns_tool_schema_instances():
    tm = ToolManager()

    def search(query: str) -> str:
        """Search the web."""
        return ""

    tm.register(search)

    schemas = tm.get_typed_tool_schemas()

    assert len(schemas) == 1
    assert isinstance(schemas[0], ToolSchema)
    assert schemas[0].name == "search"
    assert schemas[0].description == "Search the web."
    assert schemas[0].parameters["type"] == "object"
    assert "query" in schemas[0].parameters["properties"]


def test_get_typed_tool_schemas_filters_by_client_role():
    from src.core.tool_manager import ROLE_ADMIN
    tm = ToolManager()

    def public_tool() -> str:
        """Public tool."""
        return ""

    def admin_tool() -> str:
        """Admin tool."""
        return ""

    tm.register(public_tool)
    tm.register(admin_tool, required_role=ROLE_ADMIN)

    # Client with no role (public) — only sees public_tool
    schemas = tm.get_typed_tool_schemas(client_id="guest")
    assert len(schemas) == 1
    assert schemas[0].name == "public_tool"


def test_get_typed_tool_schemas_empty_when_no_tools():
    tm = ToolManager()
    assert tm.get_typed_tool_schemas() == []
