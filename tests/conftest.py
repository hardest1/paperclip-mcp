"""Shared fixtures for paperclip-mcp tests."""

from __future__ import annotations

import json
import os
from typing import Any
from unittest.mock import patch

import httpx
import pytest


@pytest.fixture(autouse=True)
def _env() -> Any:  # noqa: ANN401
    """Ensure required env vars are set for every test."""
    with patch.dict(os.environ, {
        "PAPERCLIP_API_KEY": "test-key",
        "PAPERCLIP_COMPANY_ID": "test-company-id",
        "PAPERCLIP_BASE_URL": "http://paperclip.test/api",
    }):
        import paperclip_mcp.server as srv
        srv.API_KEY = "test-key"
        srv.COMPANY = "test-company-id"
        srv.BASE_URL = "http://paperclip.test/api"
        yield


def make_response(
    status_code: int = 200,
    body: dict[str, Any] | list[Any] | None = None,
) -> httpx.Response:
    """Build a fake httpx.Response."""
    content = json.dumps(body).encode() if body is not None else b""
    return httpx.Response(
        status_code=status_code,
        content=content,
        headers={"content-type": "application/json"} if content else {},
    )
