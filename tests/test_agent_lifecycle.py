"""Tests for agent lifecycle tools (HAR-660)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from paperclip_mcp.server import (
    clear_agent_error,
    create_agent,
    pause_agent,
    resume_agent,
    terminate_agent,
    update_agent,
)


@pytest.mark.asyncio
async def test_create_agent_minimal() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "a1", "name": "Alice"}
        result = await create_agent(name="Alice", adapter_type="claude")
        mock.assert_called_once_with(
            "/companies/test-company-id/agents",
            {"name": "Alice", "adapterType": "claude"},
        )
        assert result == {"id": "a1", "name": "Alice"}


@pytest.mark.asyncio
async def test_create_agent_full() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "a1"}
        await create_agent(
            name="Bob",
            role="engineer",
            title="Sr. Engineer",
            reports_to="a0",
            capabilities="code,review",
            adapter_type="openai",
            adapter_config='{"model":"gpt-4"}',
        )
        call_body = mock.call_args[0][1]
        assert call_body["name"] == "Bob"
        assert call_body["role"] == "engineer"
        assert call_body["title"] == "Sr. Engineer"
        assert call_body["reportsTo"] == "a0"
        assert call_body["capabilities"] == "code,review"
        assert call_body["adapterType"] == "openai"
        assert call_body["adapterConfig"] == {"model": "gpt-4"}


@pytest.mark.asyncio
async def test_create_agent_invalid_adapter_config() -> None:
    result = await create_agent(name="X", adapter_type="claude", adapter_config="not json")
    assert result["isError"] is True


@pytest.mark.asyncio
async def test_update_agent() -> None:
    with patch("paperclip_mcp.server._patch", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "a1", "name": "Alice"}
        result = await update_agent(agent_id="a1", budget_monthly_cents=5000)
        mock.assert_called_once_with("/agents/a1", {"budgetMonthlyCents": 5000})
        assert result["id"] == "a1"


@pytest.mark.asyncio
async def test_update_agent_no_fields() -> None:
    result = await update_agent(agent_id="a1")
    assert result["isError"] is True


@pytest.mark.asyncio
async def test_update_agent_adapter_config_json() -> None:
    with patch("paperclip_mcp.server._patch", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "a1"}
        await update_agent(agent_id="a1", adapter_config='{"model":"sonnet"}')
        call_body = mock.call_args[0][1]
        assert call_body["adapterConfig"] == {"model": "sonnet"}


@pytest.mark.asyncio
async def test_pause_agent() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"ok": True}
        result = await pause_agent(agent_id="a1")
        mock.assert_called_once_with("/agents/a1/pause")
        assert result == {"ok": True}


@pytest.mark.asyncio
async def test_resume_agent() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"ok": True}
        result = await resume_agent(agent_id="a1")
        mock.assert_called_once_with("/agents/a1/resume")
        assert result == {"ok": True}


@pytest.mark.asyncio
async def test_clear_agent_error() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"ok": True}
        result = await clear_agent_error(agent_id="a1")
        mock.assert_called_once_with("/agents/a1/clear-error")
        assert result == {"ok": True}


@pytest.mark.asyncio
async def test_terminate_agent() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"ok": True}
        result = await terminate_agent(agent_id="a1")
        mock.assert_called_once_with("/agents/a1/terminate")
        assert result == {"ok": True}
