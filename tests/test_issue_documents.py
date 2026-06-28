"""Tests for issue document tools (HAR-663)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from paperclip_mcp.server import (
    delete_issue_document,
    get_issue_document,
    list_issue_document_revisions,
    list_issue_documents,
    upsert_issue_document,
)


@pytest.mark.asyncio
async def test_list_issue_documents() -> None:
    with patch("paperclip_mcp.server._get", new_callable=AsyncMock) as mock:
        mock.return_value = [{"key": "plan", "title": "Plan"}]
        result = await list_issue_documents(issue_id="i1")
        mock.assert_called_once_with("/issues/i1/documents")
        assert result[0]["key"] == "plan"


@pytest.mark.asyncio
async def test_get_issue_document() -> None:
    with patch("paperclip_mcp.server._get", new_callable=AsyncMock) as mock:
        mock.return_value = {"key": "plan", "title": "Plan", "body": "# Plan"}
        result = await get_issue_document(issue_id="i1", key="plan")
        mock.assert_called_once_with("/issues/i1/documents/plan")
        assert result["body"] == "# Plan"


@pytest.mark.asyncio
async def test_upsert_issue_document_create() -> None:
    with patch("paperclip_mcp.server._put", new_callable=AsyncMock) as mock:
        mock.return_value = {"key": "plan", "revisionId": "rev1"}
        result = await upsert_issue_document(
            issue_id="i1",
            key="plan",
            title="Plan",
            body="# My Plan",
        )
        call_body = mock.call_args[0][1]
        assert call_body["title"] == "Plan"
        assert call_body["format"] == "markdown"
        assert call_body["body"] == "# My Plan"
        assert "baseRevisionId" not in call_body


@pytest.mark.asyncio
async def test_upsert_issue_document_update_with_revision() -> None:
    with patch("paperclip_mcp.server._put", new_callable=AsyncMock) as mock:
        mock.return_value = {"key": "plan", "revisionId": "rev2"}
        result = await upsert_issue_document(
            issue_id="i1",
            key="plan",
            title="Plan v2",
            body="# Updated",
            base_revision_id="rev1",
        )
        call_body = mock.call_args[0][1]
        assert call_body["baseRevisionId"] == "rev1"


@pytest.mark.asyncio
async def test_upsert_issue_document_custom_format() -> None:
    with patch("paperclip_mcp.server._put", new_callable=AsyncMock) as mock:
        mock.return_value = {"key": "notes", "revisionId": "rev1"}
        await upsert_issue_document(
            issue_id="i1",
            key="notes",
            title="Notes",
            body="plain text",
            format="plaintext",
        )
        call_body = mock.call_args[0][1]
        assert call_body["format"] == "plaintext"


@pytest.mark.asyncio
async def test_list_issue_document_revisions() -> None:
    with patch("paperclip_mcp.server._get", new_callable=AsyncMock) as mock:
        mock.return_value = [{"id": "rev1"}, {"id": "rev2"}]
        result = await list_issue_document_revisions(issue_id="i1", key="plan")
        mock.assert_called_once_with("/issues/i1/documents/plan/revisions")
        assert len(result) == 2


@pytest.mark.asyncio
async def test_delete_issue_document() -> None:
    with patch("paperclip_mcp.server._delete", new_callable=AsyncMock) as mock:
        mock.return_value = {"ok": True}
        result = await delete_issue_document(issue_id="i1", key="plan")
        mock.assert_called_once_with("/issues/i1/documents/plan")
        assert result["ok"] is True
