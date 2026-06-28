"""Tests for extended cost tools (HAR-669)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from paperclip_mcp.server import (
    get_costs_by_agent,
    get_costs_by_project,
    report_cost_event,
)


@pytest.mark.asyncio
async def test_get_costs_by_agent() -> None:
    with patch("paperclip_mcp.server._get", new_callable=AsyncMock) as mock:
        mock.return_value = [{"agentId": "a1", "totalCents": 150}]
        result = await get_costs_by_agent()
        mock.assert_called_once_with(f"/companies/test-company-id/costs/by-agent")
        assert result[0]["totalCents"] == 150


@pytest.mark.asyncio
async def test_get_costs_by_project() -> None:
    with patch("paperclip_mcp.server._get", new_callable=AsyncMock) as mock:
        mock.return_value = [{"projectId": "p1", "totalCents": 300}]
        result = await get_costs_by_project()
        mock.assert_called_once_with(f"/companies/test-company-id/costs/by-project")
        assert result[0]["projectId"] == "p1"


@pytest.mark.asyncio
async def test_report_cost_event() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "ce1"}
        result = await report_cost_event(
            agent_id="a1",
            provider="openai",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500,
            cost_cents=12,
        )
        call_body = mock.call_args[0][1]
        assert call_body["agentId"] == "a1"
        assert call_body["provider"] == "openai"
        assert call_body["model"] == "gpt-4o"
        assert call_body["inputTokens"] == 1000
        assert call_body["outputTokens"] == 500
        assert call_body["costCents"] == 12
