"""Tests for extended issue fields (HAR-671)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from paperclip_mcp.server import create_issue, update_issue


@pytest.mark.asyncio
async def test_create_issue_with_goal_id() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "i1"}
        await create_issue(title="Task", goal_id="g1")
        call_body = mock.call_args[0][1]
        assert call_body["goalId"] == "g1"


@pytest.mark.asyncio
async def test_update_issue_with_goal_id() -> None:
    with patch("paperclip_mcp.server._patch", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "i1"}
        await update_issue(issue_id="i1", goal_id="g1")
        call_body = mock.call_args[0][1]
        assert call_body["goalId"] == "g1"


@pytest.mark.asyncio
async def test_update_issue_with_project_id() -> None:
    with patch("paperclip_mcp.server._patch", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "i1"}
        await update_issue(issue_id="i1", project_id="p1")
        call_body = mock.call_args[0][1]
        assert call_body["projectId"] == "p1"


@pytest.mark.asyncio
async def test_update_issue_with_parent_id() -> None:
    with patch("paperclip_mcp.server._patch", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "i1"}
        await update_issue(issue_id="i1", parent_id="i0")
        call_body = mock.call_args[0][1]
        assert call_body["parentId"] == "i0"


@pytest.mark.asyncio
async def test_update_issue_with_billing_code() -> None:
    with patch("paperclip_mcp.server._patch", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "i1"}
        await update_issue(issue_id="i1", billing_code="BC-001")
        call_body = mock.call_args[0][1]
        assert call_body["billingCode"] == "BC-001"
