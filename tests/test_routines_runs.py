"""Tests for routine runs and revisions tools (HAR-655)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from paperclip_mcp.server import (
    list_routine_revisions,
    list_routine_runs,
    restore_routine_revision,
    run_routine,
)


@pytest.mark.asyncio
async def test_run_routine_minimal() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "run1", "status": "running"}
        result = await run_routine(routine_id="r1")
        call_body = mock.call_args[0][1]
        assert call_body["source"] == "manual"
        assert result["status"] == "running"


@pytest.mark.asyncio
async def test_run_routine_full() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "run1"}
        await run_routine(
            routine_id="r1",
            trigger_id="t1",
            payload='{"key":"value"}',
            idempotency_key="idem-1",
        )
        call_body = mock.call_args[0][1]
        assert call_body["triggerId"] == "t1"
        assert call_body["payload"] == {"key": "value"}
        assert call_body["idempotencyKey"] == "idem-1"


@pytest.mark.asyncio
async def test_run_routine_invalid_payload() -> None:
    result = await run_routine(routine_id="r1", payload="not json")
    assert result["isError"] is True


@pytest.mark.asyncio
async def test_list_routine_runs_default() -> None:
    with patch("paperclip_mcp.server._get", new_callable=AsyncMock) as mock:
        mock.return_value = [{"id": "run1"}]
        result = await list_routine_runs(routine_id="r1")
        mock.assert_called_once_with(
            "/routines/r1/runs",
            {"limit": 50},
        )
        assert len(result) == 1


@pytest.mark.asyncio
async def test_list_routine_runs_custom_limit() -> None:
    with patch("paperclip_mcp.server._get", new_callable=AsyncMock) as mock:
        mock.return_value = []
        await list_routine_runs(routine_id="r1", limit=10)
        mock.assert_called_once_with("/routines/r1/runs", {"limit": 10})


@pytest.mark.asyncio
async def test_list_routine_revisions() -> None:
    with patch("paperclip_mcp.server._get", new_callable=AsyncMock) as mock:
        mock.return_value = [{"id": "rev1"}]
        result = await list_routine_revisions(routine_id="r1")
        mock.assert_called_once_with("/routines/r1/revisions")
        assert result[0]["id"] == "rev1"


@pytest.mark.asyncio
async def test_restore_routine_revision() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "rev2"}
        result = await restore_routine_revision(
            routine_id="r1",
            revision_id="rev1",
        )
        mock.assert_called_once_with(
            "/routines/r1/revisions/rev1/restore",
        )
        assert result["id"] == "rev2"
