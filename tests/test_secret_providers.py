"""Tests for secret provider vault management tools (HAR-657)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from paperclip_mcp.server import (
    check_secret_provider_health,
    create_secret_provider_config,
    disable_secret_provider_config,
    get_secret_provider_config,
    get_secret_providers_health,
    list_secret_provider_configs,
    set_default_secret_provider_config,
    update_secret_provider_config,
)


@pytest.mark.asyncio
async def test_list_secret_provider_configs() -> None:
    with patch("paperclip_mcp.server._get", new_callable=AsyncMock) as mock:
        mock.return_value = [{"id": "spc1", "provider": "local_encrypted"}]
        result = await list_secret_provider_configs()
        mock.assert_called_once_with(
            "/companies/test-company-id/secret-provider-configs",
        )
        assert result[0]["provider"] == "local_encrypted"


@pytest.mark.asyncio
async def test_get_secret_provider_config() -> None:
    with patch("paperclip_mcp.server._get", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "spc1", "displayName": "Local"}
        result = await get_secret_provider_config(config_id="spc1")
        mock.assert_called_once_with("/secret-provider-configs/spc1")
        assert result["displayName"] == "Local"


@pytest.mark.asyncio
async def test_create_secret_provider_config() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "spc1"}
        cfg = json.dumps({"region": "us-east-1"})
        result = await create_secret_provider_config(
            provider="aws_secrets_manager",
            display_name="AWS US-East",
            config=cfg,
            is_default=True,
        )
        call_body = mock.call_args[0][1]
        assert call_body["provider"] == "aws_secrets_manager"
        assert call_body["displayName"] == "AWS US-East"
        assert call_body["config"] == {"region": "us-east-1"}
        assert call_body["isDefault"] is True


@pytest.mark.asyncio
async def test_create_secret_provider_config_invalid_json() -> None:
    result = await create_secret_provider_config(
        provider="vault",
        display_name="Vault",
        config="bad json",
    )
    assert result["isError"] is True


@pytest.mark.asyncio
async def test_update_secret_provider_config() -> None:
    with patch("paperclip_mcp.server._patch", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "spc1"}
        cfg = json.dumps({"region": "eu-west-1"})
        await update_secret_provider_config(
            config_id="spc1",
            display_name="AWS EU",
            config=cfg,
        )
        call_body = mock.call_args[0][1]
        assert call_body["displayName"] == "AWS EU"
        assert call_body["config"] == {"region": "eu-west-1"}


@pytest.mark.asyncio
async def test_update_secret_provider_config_invalid_json() -> None:
    result = await update_secret_provider_config(
        config_id="spc1",
        config="bad",
    )
    assert result["isError"] is True


@pytest.mark.asyncio
async def test_disable_secret_provider_config() -> None:
    with patch("paperclip_mcp.server._delete", new_callable=AsyncMock) as mock:
        mock.return_value = {"ok": True}
        result = await disable_secret_provider_config(config_id="spc1")
        mock.assert_called_once_with("/secret-provider-configs/spc1")
        assert result["ok"] is True


@pytest.mark.asyncio
async def test_set_default_secret_provider_config() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"ok": True}
        result = await set_default_secret_provider_config(config_id="spc1")
        mock.assert_called_once_with("/secret-provider-configs/spc1/default")


@pytest.mark.asyncio
async def test_check_secret_provider_health() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"status": "healthy"}
        result = await check_secret_provider_health(config_id="spc1")
        mock.assert_called_once_with("/secret-provider-configs/spc1/health")
        assert result["status"] == "healthy"


@pytest.mark.asyncio
async def test_get_secret_providers_health() -> None:
    with patch("paperclip_mcp.server._get", new_callable=AsyncMock) as mock:
        mock.return_value = {"overall": "healthy"}
        result = await get_secret_providers_health()
        mock.assert_called_once_with(
            "/companies/test-company-id/secret-providers/health",
        )
        assert result["overall"] == "healthy"
