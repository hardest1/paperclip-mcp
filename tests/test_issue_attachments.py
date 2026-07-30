"""Tests for issue attachment tools (HAR-664)."""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from paperclip_mcp import server as srv
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
    with patch("paperclip_mcp.server._download_file", new_callable=AsyncMock) as mock:
        mock.return_value = {
            "contentBase64": "base64data",
            "contentType": "application/pdf",
        }
        result = await download_attachment(attachment_id="att1")
        mock.assert_called_once_with("/attachments/att1/content")
        assert result["contentType"] == "application/pdf"


@pytest.mark.asyncio
async def test_download_file_encodes_binary_response() -> None:
    response = httpx.Response(
        status_code=200,
        content=b"\x00binary\xff",
        headers={
            "content-type": "application/octet-stream",
            "content-disposition": 'attachment; filename="blob.bin"',
        },
        request=httpx.Request("GET", "http://paperclip.test/api/attachments/att1/content"),
    )
    with patch("paperclip_mcp.server.httpx.AsyncClient") as client_class:
        client = client_class.return_value.__aenter__.return_value
        client.get = AsyncMock(return_value=response)
        result = await srv._download_file("/attachments/att1/content")
        client.get.assert_awaited_once()
        assert result == {
            "contentBase64": base64.b64encode(b"\x00binary\xff").decode("ascii"),
            "contentType": "application/octet-stream",
            "contentDisposition": 'attachment; filename="blob.bin"',
            "sizeBytes": 8,
        }


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
async def test_upload_issue_attachment_rejects_noncanonical_base64() -> None:
    with patch("paperclip_mcp.server._upload_file", new_callable=AsyncMock) as mock:
        result = await upload_issue_attachment(
            issue_id="i1",
            filename="hello.txt",
            content_base64="YWJj\n",
        )
        assert result["isError"] is True
        mock.assert_not_called()


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
