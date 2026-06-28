"""Tests for routine trigger management tools (HAR-654)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from paperclip_mcp.server import (
    add_routine_trigger,
    delete_routine_trigger,
    rotate_trigger_secret,
    update_routine_trigger,
)


@pytest.mark.asyncio
async def test_add_schedule_trigger() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "t1", "kind": "schedule"}
        result = await add_routine_trigger(
            routine_id="r1",
            kind="schedule",
            cron_expression="0 9 * * *",
            timezone="Europe/Berlin",
        )
        call_body = mock.call_args[0][1]
        assert call_body["kind"] == "schedule"
        assert call_body["cronExpression"] == "0 9 * * *"
        assert call_body["timezone"] == "Europe/Berlin"
        assert result["kind"] == "schedule"


@pytest.mark.asyncio
async def test_add_webhook_trigger() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "t1", "kind": "webhook"}
        result = await add_routine_trigger(
            routine_id="r1",
            kind="webhook",
            signing_mode="hmac_sha256",
            replay_window_sec=300,
        )
        call_body = mock.call_args[0][1]
        assert call_body["kind"] == "webhook"
        assert call_body["signingMode"] == "hmac_sha256"
        assert call_body["replayWindowSec"] == 300


@pytest.mark.asyncio
async def test_add_api_trigger() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "t1", "kind": "api"}
        result = await add_routine_trigger(routine_id="r1", kind="api")
        call_body = mock.call_args[0][1]
        assert call_body == {"kind": "api"}


@pytest.mark.asyncio
async def test_add_trigger_invalid_kind() -> None:
    result = await add_routine_trigger(routine_id="r1", kind="invalid")
    assert result["isError"] is True


@pytest.mark.asyncio
async def test_add_trigger_replay_window_too_low() -> None:
    result = await add_routine_trigger(
        routine_id="r1",
        kind="webhook",
        replay_window_sec=10,
    )
    assert result["isError"] is True


@pytest.mark.asyncio
async def test_add_trigger_replay_window_too_high() -> None:
    result = await add_routine_trigger(
        routine_id="r1",
        kind="webhook",
        replay_window_sec=100000,
    )
    assert result["isError"] is True


@pytest.mark.asyncio
async def test_update_routine_trigger() -> None:
    with patch("paperclip_mcp.server._patch", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "t1"}
        result = await update_routine_trigger(
            trigger_id="t1",
            enabled=False,
            cron_expression="0 18 * * *",
        )
        call_body = mock.call_args[0][1]
        assert call_body["enabled"] is False
        assert call_body["cronExpression"] == "0 18 * * *"


@pytest.mark.asyncio
async def test_delete_routine_trigger() -> None:
    with patch("paperclip_mcp.server._delete", new_callable=AsyncMock) as mock:
        mock.return_value = {"ok": True}
        result = await delete_routine_trigger(trigger_id="t1")
        mock.assert_called_once_with("/routine-triggers/t1")
        assert result == {"ok": True}


@pytest.mark.asyncio
async def test_rotate_trigger_secret() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"secret": "new-secret"}
        result = await rotate_trigger_secret(trigger_id="t1")
        mock.assert_called_once_with("/routine-triggers/t1/rotate-secret")
        assert result["secret"] == "new-secret"
