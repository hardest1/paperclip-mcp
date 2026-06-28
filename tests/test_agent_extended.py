"""Tests for agent API keys, config revisions, org chart, adapter models (HAR-661)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from paperclip_mcp.server import (
    create_agent_api_key,
    get_org_chart,
    list_adapter_models,
    list_agent_config_revisions,
    rollback_agent_config,
)


@pytest.mark.asyncio
async def test_create_agent_api_key() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"key": "sk-abc123"}
        result = await create_agent_api_key(agent_id="a1")
        mock.assert_called_once_with("/agents/a1/keys")
        assert result["key"] == "sk-abc123"


@pytest.mark.asyncio
async def test_list_agent_config_revisions() -> None:
    with patch("paperclip_mcp.server._get", new_callable=AsyncMock) as mock:
        mock.return_value = [{"id": "rev1"}]
        result = await list_agent_config_revisions(agent_id="a1")
        mock.assert_called_once_with("/agents/a1/config-revisions")


@pytest.mark.asyncio
async def test_rollback_agent_config() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "rev2"}
        result = await rollback_agent_config(
            agent_id="a1", revision_id="rev1",
        )
        mock.assert_called_once_with(
            "/agents/a1/config-revisions/rev1/rollback",
        )


@pytest.mark.asyncio
async def test_get_org_chart() -> None:
    with patch("paperclip_mcp.server._get", new_callable=AsyncMock) as mock:
        mock.return_value = {"root": {"name": "CEO"}}
        result = await get_org_chart()
        mock.assert_called_once_with("/companies/test-company-id/org")


@pytest.mark.asyncio
async def test_list_adapter_models() -> None:
    with patch("paperclip_mcp.server._get", new_callable=AsyncMock) as mock:
        mock.return_value = [{"id": "claude-sonnet"}]
        result = await list_adapter_models(adapter_type="claude")
        mock.assert_called_once_with(
            "/companies/test-company-id/adapters/claude/models",
        )
