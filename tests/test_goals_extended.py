"""Tests for extended goals tools (HAR-667)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from paperclip_mcp.server import create_goal, get_goal, update_goal


@pytest.mark.asyncio
async def test_get_goal() -> None:
    with patch("paperclip_mcp.server._get", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "g1", "title": "Revenue"}
        result = await get_goal(goal_id="g1")
        mock.assert_called_once_with("/goals/g1")
        assert result["title"] == "Revenue"


@pytest.mark.asyncio
async def test_create_goal_with_level_and_status() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "g1"}
        await create_goal(
            title="Q3 Revenue",
            level="company",
            status="planned",
        )
        call_body = mock.call_args[0][1]
        assert call_body["level"] == "company"
        assert call_body["status"] == "planned"


@pytest.mark.asyncio
async def test_create_goal_invalid_level() -> None:
    result = await create_goal(title="X", level="invalid")
    assert result["isError"] is True


@pytest.mark.asyncio
async def test_create_goal_invalid_status() -> None:
    result = await create_goal(title="X", status="invalid")
    assert result["isError"] is True


@pytest.mark.asyncio
async def test_update_goal_with_status() -> None:
    with patch("paperclip_mcp.server._patch", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "g1"}
        await update_goal(goal_id="g1", status="achieved")
        call_body = mock.call_args[0][1]
        assert call_body["status"] == "achieved"


@pytest.mark.asyncio
async def test_update_goal_invalid_status() -> None:
    result = await update_goal(goal_id="g1", status="invalid")
    assert result["isError"] is True
