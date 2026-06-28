"""Tests for issue interaction tools (HAR-662)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from paperclip_mcp.server import (
    accept_issue_interaction,
    create_issue_interaction,
    list_issue_interactions,
    reject_issue_interaction,
    respond_to_issue_interaction,
)


@pytest.mark.asyncio
async def test_list_issue_interactions() -> None:
    with patch("paperclip_mcp.server._get", new_callable=AsyncMock) as mock:
        mock.return_value = [{"id": "int1", "kind": "request_confirmation"}]
        result = await list_issue_interactions(issue_id="i1")
        mock.assert_called_once_with("/issues/i1/interactions")


@pytest.mark.asyncio
async def test_create_issue_interaction() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "int1"}
        result = await create_issue_interaction(
            issue_id="i1",
            kind="request_confirmation",
            title="Deploy?",
            payload='{"prompt":"Ready to deploy?"}',
        )
        call_body = mock.call_args[0][1]
        assert call_body["kind"] == "request_confirmation"
        assert call_body["title"] == "Deploy?"
        assert call_body["payload"] == {"prompt": "Ready to deploy?"}


@pytest.mark.asyncio
async def test_create_issue_interaction_invalid_kind() -> None:
    result = await create_issue_interaction(
        issue_id="i1",
        kind="invalid",
        title="X",
    )
    assert result["isError"] is True


@pytest.mark.asyncio
async def test_create_issue_interaction_invalid_payload() -> None:
    result = await create_issue_interaction(
        issue_id="i1",
        kind="suggest_tasks",
        title="X",
        payload="bad json",
    )
    assert result["isError"] is True


@pytest.mark.asyncio
async def test_create_issue_interaction_full() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "int1"}
        await create_issue_interaction(
            issue_id="i1",
            kind="ask_user_questions",
            title="Clarify",
            summary="Need input",
            idempotency_key="idem-1",
            continuation_policy="block",
        )
        call_body = mock.call_args[0][1]
        assert call_body["summary"] == "Need input"
        assert call_body["idempotencyKey"] == "idem-1"
        assert call_body["continuationPolicy"] == "block"


@pytest.mark.asyncio
async def test_accept_issue_interaction() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"ok": True}
        result = await accept_issue_interaction(
            issue_id="i1", interaction_id="int1",
        )
        mock.assert_called_once_with("/issues/i1/interactions/int1/accept")


@pytest.mark.asyncio
async def test_reject_issue_interaction() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"ok": True}
        result = await reject_issue_interaction(
            issue_id="i1", interaction_id="int1",
        )
        mock.assert_called_once_with("/issues/i1/interactions/int1/reject")


@pytest.mark.asyncio
async def test_respond_to_issue_interaction() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"ok": True}
        result = await respond_to_issue_interaction(
            issue_id="i1",
            interaction_id="int1",
            response='{"answer":"yes"}',
        )
        call_body = mock.call_args[0][1]
        assert call_body == {"answer": "yes"}


@pytest.mark.asyncio
async def test_respond_to_issue_interaction_invalid_json() -> None:
    result = await respond_to_issue_interaction(
        issue_id="i1",
        interaction_id="int1",
        response="bad",
    )
    assert result["isError"] is True
