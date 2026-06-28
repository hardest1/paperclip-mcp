"""Tests for projects CRUD and workspace management tools (HAR-666)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from paperclip_mcp.server import (
    add_project_workspace,
    create_project,
    delete_project_workspace,
    get_project,
    list_project_workspaces,
    list_projects,
    update_project,
    update_project_workspace,
)


# ── Project CRUD ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_projects() -> None:
    with patch("paperclip_mcp.server._get", new_callable=AsyncMock) as mock:
        mock.return_value = [{"id": "p1", "name": "Alpha"}]
        result = await list_projects()
        mock.assert_called_once_with(f"/companies/test-company-id/projects")
        assert result[0]["name"] == "Alpha"


@pytest.mark.asyncio
async def test_get_project() -> None:
    with patch("paperclip_mcp.server._get", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "p1", "name": "Alpha"}
        result = await get_project(project_id="p1")
        mock.assert_called_once_with("/projects/p1")
        assert result["id"] == "p1"


@pytest.mark.asyncio
async def test_create_project_minimal() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "p1"}
        result = await create_project(name="Alpha")
        call_body = mock.call_args[0][1]
        assert call_body["name"] == "Alpha"
        assert "workspace" not in call_body


@pytest.mark.asyncio
async def test_create_project_full() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "p1"}
        await create_project(
            name="Alpha",
            description="Main project",
            goal_ids="g1,g2",
            status="active",
            workspace_name="main",
            workspace_repo_url="https://github.com/org/repo",
            workspace_repo_ref="main",
            workspace_is_primary=True,
        )
        call_body = mock.call_args[0][1]
        assert call_body["description"] == "Main project"
        assert call_body["goalIds"] == ["g1", "g2"]
        assert call_body["status"] == "active"
        assert call_body["workspace"]["name"] == "main"
        assert call_body["workspace"]["repoUrl"] == "https://github.com/org/repo"
        assert call_body["workspace"]["repoRef"] == "main"
        assert call_body["workspace"]["isPrimary"] is True


@pytest.mark.asyncio
async def test_create_project_workspace_with_cwd() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "p1"}
        await create_project(
            name="Beta",
            workspace_name="local",
            workspace_cwd="/home/user/project",
        )
        call_body = mock.call_args[0][1]
        assert call_body["workspace"]["cwd"] == "/home/user/project"


@pytest.mark.asyncio
async def test_update_project() -> None:
    with patch("paperclip_mcp.server._patch", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "p1"}
        result = await update_project(project_id="p1", status="completed")
        mock.assert_called_once_with("/projects/p1", {"status": "completed"})


@pytest.mark.asyncio
async def test_update_project_no_fields() -> None:
    result = await update_project(project_id="p1")
    assert result["isError"] is True


# ── Workspace CRUD ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_project_workspaces() -> None:
    with patch("paperclip_mcp.server._get", new_callable=AsyncMock) as mock:
        mock.return_value = [{"id": "w1"}]
        result = await list_project_workspaces(project_id="p1")
        mock.assert_called_once_with("/projects/p1/workspaces")


@pytest.mark.asyncio
async def test_add_project_workspace() -> None:
    with patch("paperclip_mcp.server._post", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "w1"}
        result = await add_project_workspace(
            project_id="p1",
            name="staging",
            repo_url="https://github.com/org/repo",
        )
        call_body = mock.call_args[0][1]
        assert call_body["name"] == "staging"
        assert call_body["repoUrl"] == "https://github.com/org/repo"


@pytest.mark.asyncio
async def test_update_project_workspace() -> None:
    with patch("paperclip_mcp.server._patch", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "w1"}
        result = await update_project_workspace(
            project_id="p1",
            workspace_id="w1",
            repo_ref="develop",
        )
        call_body = mock.call_args[0][1]
        assert call_body["repoRef"] == "develop"


@pytest.mark.asyncio
async def test_update_project_workspace_no_fields() -> None:
    result = await update_project_workspace(
        project_id="p1",
        workspace_id="w1",
    )
    assert result["isError"] is True


@pytest.mark.asyncio
async def test_delete_project_workspace() -> None:
    with patch("paperclip_mcp.server._delete", new_callable=AsyncMock) as mock:
        mock.return_value = {"ok": True}
        result = await delete_project_workspace(
            project_id="p1",
            workspace_id="w1",
        )
        mock.assert_called_once_with("/projects/p1/workspaces/w1")
