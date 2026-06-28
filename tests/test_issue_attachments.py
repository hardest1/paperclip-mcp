"""Tests for issue attachment tools (HAR-664)."""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, patch

import pytest

from paperclip_mcp.server import (
    delete_attachment,
    download_attachment,
    list_issue_attachments,
    upload_issue_attachment,
)


@pytest.mark.asyncio
async def test_list_issue_attachments() -> None:
    with patch("paperclip_mcp.server._get", new_callable=AsyncMock) as mock:
        mock.return_value = [{"id": "att1", "filename": "report.pdf"}]
        result = await list_issue_attachments(issue_id="i1")
        mock.assert_called_once_with("/issues/i1/attachments")
        assert result[0]["filename"] == "report.pdf"


@pytest.mark.asyncio
async def test_download_attachment() -> None:
    with patch("paperclip_mcp.server._get", new_callable=AsyncMock) as mock:
        mock.return_value = {"content": "base64data", "filename": "report.pdf"}
        result = await download_attachment(attachment_id="att1")
        mock.assert_called_once_with("/attachments/att1/content")


@pytest.mark.asyncio
async def test_delete_attachment() -> None:
    with patch("paperclip_mcp.server._delete", new_callable=AsyncMock) as mock:
        mock.return_value = {"ok": True}
        result = await delete_attachment(attachment_id="att1")
        mock.assert_called_once_with("/attachments/att1")
        assert result["ok"] is True


@pytest.mark.asyncio
async def test_upload_issue_attachment() -> None:
    content_b64 = base64.b64encode(b"hello world").decode()
    with patch("paperclip_mcp.server._upload_file", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "att1", "filename": "hello.txt"}
        result = await upload_issue_attachment(
            issue_id="i1",
            filename="hello.txt",
            content_base64=content_b64,
        )
        call_args = mock.call_args
        assert call_args[0][0] == "/companies/test-company-id/issues/i1/attachments"
        assert call_args[0][1] == "hello.txt"
        assert call_args[0][2] == b"hello world"


@pytest.mark.asyncio
async def test_upload_issue_attachment_invalid_base64() -> None:
    result = await upload_issue_attachment(
        issue_id="i1",
        filename="hello.txt",
        content_base64="!!!not-base64!!!",
    )
    assert result["isError"] is True


@pytest.mark.asyncio
async def test_upload_issue_attachment_with_content_type() -> None:
    content_b64 = base64.b64encode(b"pdf-data").decode()
    with patch("paperclip_mcp.server._upload_file", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "att1"}
        await upload_issue_attachment(
            issue_id="i1",
            filename="report.pdf",
            content_base64=content_b64,
            content_type="application/pdf",
        )
        call_args = mock.call_args
        assert call_args[0][3] == "application/pdf"
