"""Tests for secrets CRUD and rotation tools (HAR-656)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from paperclip_mcp.server import create_secret, list_secrets, rotate_secret


@pytest.mark.asyncio
async def test_list_secrets() -> None:
    with patch("paperclip_mcp.server._get", new_callable=AsyncMock) as mock:
        mock.return_value = [{"id": "s1", "name": "API_KEY"}]
        result = await list_secrets()
        mock.assert_called_once_with("/companies/test-company-id/secrets")
        assert result[0]["name"] == "API_KEY"


@pytest.mark.asyncio
async def test_create_secret_basic() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "s1"}
        result = await create_secret(name="DB_PASSWORD", value="hunter2")
        call_body = mock.call_args[0][1]
        assert call_body["name"] == "DB_PASSWORD"
        assert call_body["value"] == "hunter2"


@pytest.mark.asyncio
async def test_create_secret_external_ref() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "s1"}
        await create_secret(
            name="EXT_SECRET",
            provider="aws_secrets_manager",
            managed_mode="external_reference",
            external_ref="arn:aws:secretsmanager:us-east-1:123:secret:prod",
            provider_version_ref="v1",
            provider_config_id="vpc-1",
        )
        call_body = mock.call_args[0][1]
        assert call_body["provider"] == "aws_secrets_manager"
        assert call_body["managedMode"] == "external_reference"
        assert call_body["externalRef"].startswith("arn:")
        assert call_body["providerVersionRef"] == "v1"
        assert call_body["providerConfigId"] == "vpc-1"


@pytest.mark.asyncio
async def test_rotate_secret() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "s1", "version": 2}
        result = await rotate_secret(secret_id="s1", value="new-pass")
        call_body = mock.call_args[0][1]
        assert call_body["value"] == "new-pass"


@pytest.mark.asyncio
async def test_rotate_secret_with_provider_config() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "s1"}
        await rotate_secret(
            secret_id="s1",
            value="new-pass",
            provider_config_id="vpc-1",
        )
        call_body = mock.call_args[0][1]
        assert call_body["providerConfigId"] == "vpc-1"
