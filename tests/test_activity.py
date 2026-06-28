"""Tests for activity tool filters (HAR-670)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from paperclip_mcp.server import list_activity


@pytest.mark.asyncio
async def test_list_activity_defaults() -> None:
    with patch("paperclip_mcp.server._get", new_callable=AsyncMock) as mock:
        mock.return_value = [{"id": "act1"}]
        result = await list_activity()
        mock.assert_called_once_with(
            "/companies/test-company-id/activity",
            {"limit": 20},
        )


@pytest.mark.asyncio
async def test_list_activity_with_agent_id() -> None:
    with patch("paperclip_mcp.server._get", new_callable=AsyncMock) as mock:
        mock.return_value = []
        await list_activity(agent_id="a1")
        params = mock.call_args[0][1]
        assert params["agentId"] == "a1"


@pytest.mark.asyncio
async def test_list_activity_with_entity_type() -> None:
    with patch("paperclip_mcp.server._get", new_callable=AsyncMock) as mock:
        mock.return_value = []
        await list_activity(entity_type="issue")
        params = mock.call_args[0][1]
        assert params["entityType"] == "issue"


@pytest.mark.asyncio
async def test_list_activity_with_entity_id() -> None:
    with patch("paperclip_mcp.server._get", new_callable=AsyncMock) as mock:
        mock.return_value = []
        await list_activity(entity_id="i1")
        params = mock.call_args[0][1]
        assert params["entityId"] == "i1"


@pytest.mark.asyncio
async def test_list_activity_invalid_entity_type() -> None:
    result = await list_activity(entity_type="invalid")
    assert result["isError"] is True


@pytest.mark.asyncio
async def test_list_activity_all_filters() -> None:
    with patch("paperclip_mcp.server._get", new_callable=AsyncMock) as mock:
        mock.return_value = []
        await list_activity(
            agent_id="a1",
            entity_type="approval",
            entity_id="ap1",
            limit=5,
        )
        params = mock.call_args[0][1]
        assert params["agentId"] == "a1"
        assert params["entityType"] == "approval"
        assert params["entityId"] == "ap1"
        assert params["limit"] == 5
