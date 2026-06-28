"""Tests for issue comments tools (HAR-665)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from paperclip_mcp.server import list_issue_comments


@pytest.mark.asyncio
async def test_list_issue_comments() -> None:
    with patch("paperclip_mcp.server._get", new_callable=AsyncMock) as mock:
        mock.return_value = [{"id": "c1", "body": "Hello"}]
        result = await list_issue_comments(issue_id="i1")
        mock.assert_called_once_with("/issues/i1/comments")
        assert result[0]["body"] == "Hello"
