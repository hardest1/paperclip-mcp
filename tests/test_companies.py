"""Tests for companies CRUD tools (HAR-659)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from paperclip_mcp.server import (
    archive_company,
    create_company,
    get_company,
    list_companies,
    update_company,
)


@pytest.mark.asyncio
async def test_list_companies() -> None:
    with patch("paperclip_mcp.server._get", new_callable=AsyncMock) as mock:
        mock.return_value = [{"id": "c1", "name": "Acme"}]
        result = await list_companies()
        mock.assert_called_once_with("/companies")
        assert result[0]["name"] == "Acme"


@pytest.mark.asyncio
async def test_get_company() -> None:
    with patch("paperclip_mcp.server._get", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "c1", "name": "Acme"}
        result = await get_company(company_id="c1")
        mock.assert_called_once_with("/companies/c1")


@pytest.mark.asyncio
async def test_create_company() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "c1"}
        result = await create_company(name="Acme", description="Widgets")
        call_body = mock.call_args[0][1]
        assert call_body["name"] == "Acme"
        assert call_body["description"] == "Widgets"


@pytest.mark.asyncio
async def test_update_company() -> None:
    with patch("paperclip_mcp.server._patch", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "c1"}
        await update_company(company_id="c1", budget_monthly_cents=50000)
        call_body = mock.call_args[0][1]
        assert call_body["budgetMonthlyCents"] == 50000


@pytest.mark.asyncio
async def test_update_company_no_fields() -> None:
    result = await update_company(company_id="c1")
    assert result["isError"] is True


@pytest.mark.asyncio
async def test_archive_company() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"ok": True}
        result = await archive_company(company_id="c1")
        mock.assert_called_once_with("/companies/c1/archive")
