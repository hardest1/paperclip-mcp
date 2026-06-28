"""Tests for routines CRUD tools (HAR-653)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from paperclip_mcp.server import (
    create_routine,
    get_routine,
    list_routines,
    update_routine,
)


@pytest.mark.asyncio
async def test_list_routines() -> None:
    with patch("paperclip_mcp.server._get", new_callable=AsyncMock) as mock:
        mock.return_value = [{"id": "r1", "title": "Daily sync"}]
        result = await list_routines()
        mock.assert_called_once_with(f"/companies/test-company-id/routines")
        assert result[0]["title"] == "Daily sync"


@pytest.mark.asyncio
async def test_get_routine() -> None:
    with patch("paperclip_mcp.server._get", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "r1", "title": "Daily sync"}
        result = await get_routine(routine_id="r1")
        mock.assert_called_once_with("/routines/r1")
        assert result["id"] == "r1"


@pytest.mark.asyncio
async def test_create_routine_minimal() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "r1"}
        result = await create_routine(
            title="Daily sync",
            assignee_agent_id="a1",
            project_id="p1",
        )
        call_body = mock.call_args[0][1]
        assert call_body["title"] == "Daily sync"
        assert call_body["assigneeAgentId"] == "a1"
        assert call_body["projectId"] == "p1"
        assert "concurrencyPolicy" not in call_body
        assert result["id"] == "r1"


@pytest.mark.asyncio
async def test_create_routine_full() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "r1"}
        await create_routine(
            title="Weekly report",
            assignee_agent_id="a1",
            project_id="p1",
            description="Generate weekly report",
            goal_id="g1",
            parent_issue_id="i1",
            priority="high",
            status="active",
            concurrency_policy="skip_if_active",
            catch_up_policy="enqueue_missed_with_cap",
        )
        call_body = mock.call_args[0][1]
        assert call_body["description"] == "Generate weekly report"
        assert call_body["goalId"] == "g1"
        assert call_body["parentIssueId"] == "i1"
        assert call_body["priority"] == "high"
        assert call_body["status"] == "active"
        assert call_body["concurrencyPolicy"] == "skip_if_active"
        assert call_body["catchUpPolicy"] == "enqueue_missed_with_cap"


@pytest.mark.asyncio
async def test_create_routine_invalid_concurrency_policy() -> None:
    result = await create_routine(
        title="X",
        assignee_agent_id="a1",
        project_id="p1",
        concurrency_policy="invalid",
    )
    assert result["isError"] is True


@pytest.mark.asyncio
async def test_create_routine_invalid_catch_up_policy() -> None:
    result = await create_routine(
        title="X",
        assignee_agent_id="a1",
        project_id="p1",
        catch_up_policy="invalid",
    )
    assert result["isError"] is True


@pytest.mark.asyncio
async def test_create_routine_invalid_status() -> None:
    result = await create_routine(
        title="X",
        assignee_agent_id="a1",
        project_id="p1",
        status="invalid",
    )
    assert result["isError"] is True


@pytest.mark.asyncio
async def test_update_routine() -> None:
    with patch("paperclip_mcp.server._patch", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "r1", "title": "Updated"}
        result = await update_routine(routine_id="r1", title="Updated")
        mock.assert_called_once_with("/routines/r1", {"title": "Updated"})
        assert result["title"] == "Updated"


@pytest.mark.asyncio
async def test_update_routine_with_revision() -> None:
    with patch("paperclip_mcp.server._patch", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "r1"}
        await update_routine(
            routine_id="r1",
            title="Updated",
            base_revision_id="rev-1",
        )
        call_body = mock.call_args[0][1]
        assert call_body["baseRevisionId"] == "rev-1"


@pytest.mark.asyncio
async def test_update_routine_no_fields() -> None:
    result = await update_routine(routine_id="r1")
    assert result["isError"] is True


@pytest.mark.asyncio
async def test_update_routine_invalid_status() -> None:
    result = await update_routine(routine_id="r1", status="invalid")
    assert result["isError"] is True
