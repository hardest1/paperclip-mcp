"""Tests for extended approvals tools (HAR-668)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from paperclip_mcp.server import (
    comment_on_approval,
    create_approval_request,
    create_hire_request,
    get_approval,
    list_approval_comments,
    list_approval_issues,
    resubmit_approval,
)


@pytest.mark.asyncio
async def test_get_approval() -> None:
    with patch("paperclip_mcp.server._get", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "ap1", "status": "pending"}
        result = await get_approval(approval_id="ap1")
        mock.assert_called_once_with("/approvals/ap1")
        assert result["status"] == "pending"


@pytest.mark.asyncio
async def test_create_approval_request() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "ap1"}
        result = await create_approval_request(
            approval_type="budget_increase",
            requested_by_agent_id="a1",
            payload='{"amount":5000}',
        )
        call_body = mock.call_args[0][1]
        assert call_body["type"] == "budget_increase"
        assert call_body["requestedByAgentId"] == "a1"
        assert call_body["payload"] == {"amount": 5000}


@pytest.mark.asyncio
async def test_create_approval_request_invalid_payload() -> None:
    result = await create_approval_request(
        approval_type="x",
        requested_by_agent_id="a1",
        payload="not json",
    )
    assert result["isError"] is True


@pytest.mark.asyncio
async def test_create_hire_request() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "ap1", "agentId": "a1"}
        result = await create_hire_request(
            name="New Agent",
            role="researcher",
            budget_monthly_cents=10000,
        )
        call_body = mock.call_args[0][1]
        assert call_body["name"] == "New Agent"
        assert call_body["role"] == "researcher"
        assert call_body["budgetMonthlyCents"] == 10000


@pytest.mark.asyncio
async def test_create_hire_request_full() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "ap1"}
        await create_hire_request(
            name="Agent",
            role="dev",
            reports_to="a0",
            capabilities="code",
            budget_monthly_cents=5000,
        )
        call_body = mock.call_args[0][1]
        assert call_body["reportsTo"] == "a0"
        assert call_body["capabilities"] == "code"


@pytest.mark.asyncio
async def test_resubmit_approval() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "ap1", "status": "pending"}
        result = await resubmit_approval(
            approval_id="ap1",
            payload='{"updated":true}',
        )
        call_body = mock.call_args[0][1]
        assert call_body["payload"] == {"updated": True}


@pytest.mark.asyncio
async def test_resubmit_approval_invalid_payload() -> None:
    result = await resubmit_approval(approval_id="ap1", payload="bad")
    assert result["isError"] is True


@pytest.mark.asyncio
async def test_list_approval_issues() -> None:
    with patch("paperclip_mcp.server._get", new_callable=AsyncMock) as mock:
        mock.return_value = [{"id": "i1"}]
        result = await list_approval_issues(approval_id="ap1")
        mock.assert_called_once_with("/approvals/ap1/issues")


@pytest.mark.asyncio
async def test_list_approval_comments() -> None:
    with patch("paperclip_mcp.server._get", new_callable=AsyncMock) as mock:
        mock.return_value = [{"id": "c1"}]
        result = await list_approval_comments(approval_id="ap1")
        mock.assert_called_once_with("/approvals/ap1/comments")


@pytest.mark.asyncio
async def test_comment_on_approval() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "c1"}
        result = await comment_on_approval(
            approval_id="ap1",
            body="Looks good",
        )
        call_body = mock.call_args[0][1]
        assert call_body["body"] == "Looks good"
