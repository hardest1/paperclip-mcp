#!/usr/bin/env python3
"""
paperclip-mcp — MCP server for the Paperclip AI agent orchestration platform.

Exposes Paperclip's REST API as MCP tools so that AI assistants can manage
issues, agents, goals, approvals, costs, and activity via natural language.

Documentation: https://github.com/paperclipai/paperclip
MCP spec:      https://modelcontextprotocol.io

Configuration (environment variables):
    PAPERCLIP_API_KEY      Required. Agent API key — generate in Paperclip UI:
                           Settings → API Keys → New Key.
    PAPERCLIP_COMPANY_ID   Required. Company UUID shown in the Paperclip UI URL
                           when viewing your company: /companies/{uuid}.
    PAPERCLIP_BASE_URL     Optional. Default: http://localhost:3100/api
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastmcp import FastMCP

# ── Configuration ──────────────────────────────────────────────────────────────

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional; env vars can be set by the shell

BASE_URL: str = os.environ.get("PAPERCLIP_BASE_URL", "http://localhost:3100/api").rstrip("/")
API_KEY: str  = os.environ.get("PAPERCLIP_API_KEY", "")
COMPANY: str  = os.environ.get("PAPERCLIP_COMPANY_ID", "")

# ── Logging ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] paperclip-mcp %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stderr,
)
log = logging.getLogger(__name__)

# ── HTTP client ────────────────────────────────────────────────────────────────

_HTTP_TIMEOUT = 30  # seconds


def _headers() -> dict[str, str]:
    """Build per-request headers.  Omit X-Paperclip-Run-Id — a fake UUID causes
    FK violations against heartbeat_runs when the API logs activity."""
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }


def _err(message: str, status: int | None = None) -> dict[str, Any]:
    """Return a structured error payload that signals isError to the MCP client."""
    payload: dict[str, Any] = {"isError": True, "message": message}
    if status is not None:
        payload["status"] = status
    return payload


async def _request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
) -> Any:
    url = f"{BASE_URL}{path}"
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            r = await client.request(
                method,
                url,
                headers=_headers(),
                params=params,
                json=body,
            )
            # 409 Conflict on checkout: another agent owns the issue — do not retry.
            if r.status_code == 409:
                return _err(
                    "Conflict (409): resource is already checked out or owned by another agent. "
                    "Do not retry this request.",
                    status=409,
                )
            r.raise_for_status()
            # 204 No Content
            if r.status_code == 204 or not r.content:
                return {"ok": True}
            return r.json()
    except httpx.HTTPStatusError as exc:
        return _err(
            f"HTTP {exc.response.status_code} from Paperclip API: {exc.response.text[:400]}",
            status=exc.response.status_code,
        )
    except httpx.RequestError as exc:
        return _err(
            f"Could not reach Paperclip at {BASE_URL}. "
            f"Is the server running? Error: {exc}"
        )


async def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    return await _request("GET", path, params=params)


async def _post(path: str, body: dict[str, Any] | None = None) -> Any:
    return await _request("POST", path, body=body)


async def _patch(path: str, body: dict[str, Any]) -> Any:
    return await _request("PATCH", path, body=body)


async def _delete(path: str) -> Any:
    return await _request("DELETE", path)


# ── Startup validation ─────────────────────────────────────────────────────────

def _validate_config() -> None:
    """Fail fast with actionable error messages if required env vars are missing."""
    missing = [k for k, v in {
        "PAPERCLIP_API_KEY": API_KEY,
        "PAPERCLIP_COMPANY_ID": COMPANY,
    }.items() if not v]
    if missing:
        log.error("Missing required environment variables: %s", ", ".join(missing))
        log.error(
            "Copy .env.example to .env, fill in the values, then:\n"
            "  source .env && python -m paperclip_mcp\n"
            "Or set them in your shell before starting the server."
        )
        sys.exit(1)


@asynccontextmanager
async def _lifespan(_server: FastMCP):  # type: ignore[type-arg]
    _validate_config()
    log.info("paperclip-mcp started — base: %s | company: %s", BASE_URL, COMPANY)
    yield
    log.info("paperclip-mcp stopped.")


# ── MCP Server ─────────────────────────────────────────────────────────────────

mcp = FastMCP(
    name="paperclip",
    instructions=(
        "Manage a Paperclip AI agent orchestration platform. "
        "Use these tools to create and track issues (tasks), inspect agents, "
        "set goals, handle approvals, and monitor costs. "
        "All operations target a single Paperclip company configured via "
        "PAPERCLIP_COMPANY_ID."
    ),
    lifespan=_lifespan,
)


# ── ISSUES ─────────────────────────────────────────────────────────────────────

@mcp.tool()
async def list_issues(
    status: str = "todo,in_progress",
    assignee_agent_id: str = "",
    project_id: str = "",
    label: str = "",
    limit: int = 50,
) -> Any:
    """List issues (tasks) in the active company.

    Args:
        status: Comma-separated issue statuses to include.
                Allowed values: todo, in_progress, blocked, done, cancelled.
                Default: "todo,in_progress"
        assignee_agent_id: UUID of the agent to filter by. Leave empty for all agents.
        project_id: UUID of the project to filter by. Leave empty for all projects.
        label: Label name to filter by. Leave empty to skip label filtering.
        limit: Maximum number of results to return (1–200). Default: 50.
    """
    params: dict[str, Any] = {"status": status, "limit": max(1, min(limit, 200))}
    if assignee_agent_id:
        params["assigneeAgentId"] = assignee_agent_id
    if project_id:
        params["projectId"] = project_id
    if label:
        params["label"] = label
    return await _get(f"/companies/{COMPANY}/issues", params)


@mcp.tool()
async def get_issue(issue_id: str) -> Any:
    """Get the full details of a single issue.

    Args:
        issue_id: Issue UUID or human-readable identifier (e.g. "CY-42").
    """
    return await _get(f"/issues/{issue_id}")


@mcp.tool()
async def create_issue(
    title: str,
    description: str = "",
    assignee_agent_id: str = "",
    project_id: str = "",
    parent_issue_id: str = "",
    priority: str = "medium",
) -> Any:
    """Create a new issue (task) and optionally assign it to an agent.

    Use this to delegate work to agents, create subtasks, or track action items.

    Args:
        title: Short, imperative task title (e.g. "Search cheese suppliers in Barcelona").
        description: Full instructions or context for the agent (Markdown supported).
        assignee_agent_id: UUID of the agent to assign. Leave empty to leave unassigned.
        project_id: UUID of the project this issue belongs to. Leave empty for no project.
        parent_issue_id: UUID of the parent issue when creating a subtask. Leave empty for top-level.
        priority: Task priority — urgent, high, medium, or low. Default: medium.
    """
    body: dict[str, Any] = {"title": title, "priority": priority}
    if description:
        body["description"] = description
    if assignee_agent_id:
        body["assigneeAgentId"] = assignee_agent_id
    if project_id:
        body["projectId"] = project_id
    if parent_issue_id:
        body["parentIssueId"] = parent_issue_id
    return await _post(f"/companies/{COMPANY}/issues", body)


@mcp.tool()
async def update_issue(
    issue_id: str,
    title: str = "",
    description: str = "",
    status: str = "",
    assignee_agent_id: str = "",
    priority: str = "",
) -> Any:
    """Update an existing issue. Only fields you provide are changed.

    Args:
        issue_id: Issue UUID or identifier (e.g. "CY-42").
        title: New title. Leave empty to keep current value.
        description: New description (Markdown). Leave empty to keep current.
        status: New status — todo, in_progress, blocked, done, or cancelled.
                Leave empty to keep current.
        assignee_agent_id: New agent UUID. Leave empty to keep current assignee.
        priority: New priority — urgent, high, medium, or low. Leave empty to keep current.
    """
    body: dict[str, Any] = {}
    if title:
        body["title"] = title
    if description:
        body["description"] = description
    if status:
        if status not in {"todo", "in_progress", "blocked", "done", "cancelled"}:
            return _err(f"Invalid status '{status}'. Allowed: todo, in_progress, blocked, done, cancelled.")
        body["status"] = status
    if assignee_agent_id:
        body["assigneeAgentId"] = assignee_agent_id
    if priority:
        if priority not in {"urgent", "high", "medium", "low"}:
            return _err(f"Invalid priority '{priority}'. Allowed: urgent, high, medium, low.")
        body["priority"] = priority
    if not body:
        return _err("No fields to update. Provide at least one of: title, description, status, assignee_agent_id, priority.")
    return await _patch(f"/issues/{issue_id}", body)


@mcp.tool()
async def checkout_issue(issue_id: str) -> Any:
    """Atomically assign an issue to the current agent and mark it in_progress.

    A 409 Conflict response means another agent already owns this issue — do NOT retry.
    Use release_issue to undo a checkout.

    Args:
        issue_id: Issue UUID or identifier to check out.
    """
    return await _post(f"/issues/{issue_id}/checkout")


@mcp.tool()
async def release_issue(issue_id: str) -> Any:
    """Release an issue: unassign it and revert it to its previous state.

    This is the inverse of checkout_issue. Use when an agent cannot complete a task
    and it should be returned to the queue.

    Args:
        issue_id: Issue UUID or identifier to release.
    """
    return await _post(f"/issues/{issue_id}/release")


@mcp.tool()
async def comment_on_issue(
    issue_id: str,
    body: str,
    reopen: bool = False,
) -> Any:
    """Add a comment to an issue (supports Markdown).

    Args:
        issue_id: Issue UUID or identifier.
        body: Comment text. Markdown is supported.
        reopen: Set to true to reopen the issue when posting this comment.
                Only effective if the issue is currently closed.
    """
    payload: dict[str, Any] = {"body": body}
    if reopen:
        payload["reopen"] = True
    return await _post(f"/issues/{issue_id}/comments", payload)


@mcp.tool()
async def delete_issue(issue_id: str) -> Any:
    """Permanently delete an issue. This action cannot be undone.

    Args:
        issue_id: Issue UUID or identifier to delete.
    """
    return await _delete(f"/issues/{issue_id}")


# ── AGENTS ─────────────────────────────────────────────────────────────────────

@mcp.tool()
async def list_agents() -> Any:
    """List all agents in the active company with their name, role, status, and config."""
    return await _get(f"/companies/{COMPANY}/agents")


@mcp.tool()
async def get_agent(agent_id: str = "me") -> Any:
    """Get details for a specific agent, or the currently authenticated agent.

    Args:
        agent_id: Agent UUID, or the literal string "me" to get the current agent identity.
                  Default: "me"
    """
    path = "/agents/me" if agent_id.strip().lower() == "me" else f"/agents/{agent_id}"
    return await _get(path)


@mcp.tool()
async def invoke_agent_heartbeat(agent_id: str) -> Any:
    """Manually trigger an immediate heartbeat (work cycle) for an agent.

    Use this to wake an idle agent, force it to pick up new assignments,
    or run it outside its normal schedule.

    Args:
        agent_id: UUID of the agent to trigger.
    """
    return await _post(f"/agents/{agent_id}/heartbeat/invoke")


@mcp.tool()
async def create_agent(
    name: str,
    adapter_type: str,
    role: str = "",
    title: str = "",
    reports_to: str = "",
    capabilities: str = "",
    adapter_config: str = "",
) -> Any:
    """Create a new agent in the active company.

    Args:
        name: Agent display name.
        adapter_type: LLM adapter (e.g. "claude", "openai", "custom").
        role: Agent role description (e.g. "engineer", "researcher").
        title: Job title shown in the org chart.
        reports_to: UUID of the agent this one reports to.
        capabilities: Comma-separated capability tags (e.g. "code,review").
        adapter_config: JSON string with adapter-specific settings
                        (e.g. '{"model":"claude-sonnet-4-20250514"}').
    """
    body: dict[str, Any] = {"name": name, "adapterType": adapter_type}
    if role:
        body["role"] = role
    if title:
        body["title"] = title
    if reports_to:
        body["reportsTo"] = reports_to
    if capabilities:
        body["capabilities"] = capabilities
    if adapter_config:
        import json as _json

        try:
            body["adapterConfig"] = _json.loads(adapter_config)
        except _json.JSONDecodeError:
            return _err(
                "adapter_config must be valid JSON "
                '(e.g. \'{"model":"claude-sonnet-4-20250514"}\').'
            )
    return await _post(f"/companies/{COMPANY}/agents", body)


@mcp.tool()
async def update_agent(
    agent_id: str,
    name: str = "",
    role: str = "",
    title: str = "",
    adapter_config: str = "",
    budget_monthly_cents: int = 0,
) -> Any:
    """Update an existing agent. Only fields you provide are changed.

    Args:
        agent_id: Agent UUID.
        name: New display name.
        role: New role description.
        title: New job title.
        adapter_config: JSON string with new adapter settings.
        budget_monthly_cents: Monthly budget cap in cents (0 to skip).
    """
    body: dict[str, Any] = {}
    if name:
        body["name"] = name
    if role:
        body["role"] = role
    if title:
        body["title"] = title
    if adapter_config:
        import json as _json

        try:
            body["adapterConfig"] = _json.loads(adapter_config)
        except _json.JSONDecodeError:
            return _err(
                "adapter_config must be valid JSON "
                '(e.g. \'{"model":"claude-sonnet-4-20250514"}\').'
            )
    if budget_monthly_cents:
        body["budgetMonthlyCents"] = budget_monthly_cents
    if not body:
        return _err(
            "No fields to update. Provide at least one of: "
            "name, role, title, adapter_config, budget_monthly_cents."
        )
    return await _patch(f"/agents/{agent_id}", body)


@mcp.tool()
async def pause_agent(agent_id: str) -> Any:
    """Temporarily pause an agent, stopping its heartbeat cycles.

    The agent keeps its configuration and can be resumed later.

    Args:
        agent_id: UUID of the agent to pause.
    """
    return await _post(f"/agents/{agent_id}/pause")


@mcp.tool()
async def resume_agent(agent_id: str) -> Any:
    """Resume a paused agent, restarting its heartbeat cycles.

    Args:
        agent_id: UUID of the agent to resume.
    """
    return await _post(f"/agents/{agent_id}/resume")


@mcp.tool()
async def clear_agent_error(agent_id: str) -> Any:
    """Clear an agent's error state, moving it back to idle.

    Only works when the agent is currently in an error state.

    Args:
        agent_id: UUID of the agent in error state.
    """
    return await _post(f"/agents/{agent_id}/clear-error")


@mcp.tool()
async def terminate_agent(agent_id: str) -> Any:
    """PERMANENTLY deactivate an agent. THIS ACTION CANNOT BE UNDONE.

    The agent will stop all work immediately and cannot be resumed or
    restarted. Use pause_agent instead if you want a reversible stop.

    Args:
        agent_id: UUID of the agent to terminate.
    """
    return await _post(f"/agents/{agent_id}/terminate")


# ── ROUTINES ──────────────────────────────────────────────────────────────────

_CONCURRENCY_POLICIES = {"coalesce_if_active", "skip_if_active", "always_enqueue"}
_CATCH_UP_POLICIES = {"skip_missed", "enqueue_missed_with_cap"}
_ROUTINE_STATUSES = {"active", "paused", "archived"}


@mcp.tool()
async def list_routines() -> Any:
    """List all routines for the active company."""
    return await _get(f"/companies/{COMPANY}/routines")


@mcp.tool()
async def get_routine(routine_id: str) -> Any:
    """Get full details of a routine including its triggers.

    Args:
        routine_id: Routine UUID.
    """
    return await _get(f"/routines/{routine_id}")


@mcp.tool()
async def create_routine(
    title: str,
    assignee_agent_id: str,
    project_id: str,
    description: str = "",
    goal_id: str = "",
    parent_issue_id: str = "",
    priority: str = "",
    status: str = "",
    concurrency_policy: str = "",
    catch_up_policy: str = "",
) -> Any:
    """Create a new routine (recurring task).

    Args:
        title: Short routine title.
        assignee_agent_id: UUID of the agent that executes the routine.
        project_id: UUID of the project this routine belongs to.
        description: Extended instructions (Markdown).
        goal_id: UUID of the goal to link this routine to.
        parent_issue_id: UUID of a parent issue for subtask grouping.
        priority: urgent, high, medium, or low.
        status: active, paused, or archived. Default: active.
        concurrency_policy: coalesce_if_active (default),
                            skip_if_active, or always_enqueue.
        catch_up_policy: skip_missed (default) or
                         enqueue_missed_with_cap.
    """
    if concurrency_policy and concurrency_policy not in _CONCURRENCY_POLICIES:
        return _err(
            f"Invalid concurrency_policy '{concurrency_policy}'. "
            f"Allowed: {', '.join(sorted(_CONCURRENCY_POLICIES))}."
        )
    if catch_up_policy and catch_up_policy not in _CATCH_UP_POLICIES:
        return _err(
            f"Invalid catch_up_policy '{catch_up_policy}'. "
            f"Allowed: {', '.join(sorted(_CATCH_UP_POLICIES))}."
        )
    if status and status not in _ROUTINE_STATUSES:
        return _err(
            f"Invalid status '{status}'. "
            f"Allowed: {', '.join(sorted(_ROUTINE_STATUSES))}."
        )
    body: dict[str, Any] = {
        "title": title,
        "assigneeAgentId": assignee_agent_id,
        "projectId": project_id,
    }
    if description:
        body["description"] = description
    if goal_id:
        body["goalId"] = goal_id
    if parent_issue_id:
        body["parentIssueId"] = parent_issue_id
    if priority:
        body["priority"] = priority
    if status:
        body["status"] = status
    if concurrency_policy:
        body["concurrencyPolicy"] = concurrency_policy
    if catch_up_policy:
        body["catchUpPolicy"] = catch_up_policy
    return await _post(f"/companies/{COMPANY}/routines", body)


@mcp.tool()
async def update_routine(
    routine_id: str,
    title: str = "",
    description: str = "",
    status: str = "",
    concurrency_policy: str = "",
    catch_up_policy: str = "",
    base_revision_id: str = "",
) -> Any:
    """Update an existing routine. Only fields you provide are changed.

    Args:
        routine_id: Routine UUID.
        title: New title.
        description: New description (Markdown).
        status: New status — active, paused, or archived.
        concurrency_policy: coalesce_if_active, skip_if_active,
                            or always_enqueue.
        catch_up_policy: skip_missed or enqueue_missed_with_cap.
        base_revision_id: Revision UUID for optimistic concurrency.
                          Returns 409 if the routine was modified since
                          this revision.
    """
    if status and status not in _ROUTINE_STATUSES:
        return _err(
            f"Invalid status '{status}'. "
            f"Allowed: {', '.join(sorted(_ROUTINE_STATUSES))}."
        )
    if concurrency_policy and concurrency_policy not in _CONCURRENCY_POLICIES:
        return _err(
            f"Invalid concurrency_policy '{concurrency_policy}'. "
            f"Allowed: {', '.join(sorted(_CONCURRENCY_POLICIES))}."
        )
    if catch_up_policy and catch_up_policy not in _CATCH_UP_POLICIES:
        return _err(
            f"Invalid catch_up_policy '{catch_up_policy}'. "
            f"Allowed: {', '.join(sorted(_CATCH_UP_POLICIES))}."
        )
    body: dict[str, Any] = {}
    if title:
        body["title"] = title
    if description:
        body["description"] = description
    if status:
        body["status"] = status
    if concurrency_policy:
        body["concurrencyPolicy"] = concurrency_policy
    if catch_up_policy:
        body["catchUpPolicy"] = catch_up_policy
    if base_revision_id:
        body["baseRevisionId"] = base_revision_id
    if not body:
        return _err(
            "No fields to update. Provide at least one of: "
            "title, description, status, concurrency_policy, catch_up_policy."
        )
    return await _patch(f"/routines/{routine_id}", body)


# ── GOALS ──────────────────────────────────────────────────────────────────────

@mcp.tool()
async def list_goals() -> Any:
    """List all strategic goals and projects for the active company."""
    return await _get(f"/companies/{COMPANY}/goals")


@mcp.tool()
async def create_goal(title: str, description: str = "") -> Any:
    """Create a new strategic goal for the active company.

    Goals provide high-level direction to agents. They appear in agent context
    so agents can align their work accordingly.

    Args:
        title: Goal title (e.g. "Reach 300 packs/month in sales by June 2026").
        description: Extended context, success criteria, and constraints (Markdown supported).
    """
    body: dict[str, Any] = {"title": title}
    if description:
        body["description"] = description
    return await _post(f"/companies/{COMPANY}/goals", body)


@mcp.tool()
async def update_goal(
    goal_id: str,
    title: str = "",
    description: str = "",
) -> Any:
    """Update an existing goal's title or description.

    Args:
        goal_id: Goal UUID.
        title: New title. Leave empty to keep current.
        description: New description. Leave empty to keep current.
    """
    body: dict[str, Any] = {}
    if title:
        body["title"] = title
    if description:
        body["description"] = description
    if not body:
        return _err("No fields to update. Provide at least one of: title, description.")
    return await _patch(f"/goals/{goal_id}", body)


# ── APPROVALS ──────────────────────────────────────────────────────────────────

@mcp.tool()
async def list_approvals(status: str = "pending") -> Any:
    """List approval requests in the active company.

    Args:
        status: Filter by status. Allowed values:
                pending, approved, rejected, revision_requested.
                Default: "pending"
    """
    allowed = {"pending", "approved", "rejected", "revision_requested"}
    if status not in allowed:
        return _err(f"Invalid status '{status}'. Allowed: {', '.join(sorted(allowed))}.")
    return await _get(f"/companies/{COMPANY}/approvals", {"status": status})


@mcp.tool()
async def approve(approval_id: str, comment: str = "") -> Any:
    """Approve a pending approval request.

    Args:
        approval_id: Approval UUID.
        comment: Optional approval note to attach (e.g. conditions, context).
    """
    body: dict[str, Any] = {}
    if comment:
        body["comment"] = comment
    return await _post(f"/approvals/{approval_id}/approve", body)


@mcp.tool()
async def reject(approval_id: str, comment: str = "") -> Any:
    """Reject a pending approval request.

    Args:
        approval_id: Approval UUID.
        comment: Reason for rejection — strongly recommended so the agent understands why.
    """
    body: dict[str, Any] = {}
    if comment:
        body["comment"] = comment
    return await _post(f"/approvals/{approval_id}/reject", body)


@mcp.tool()
async def request_approval_revision(approval_id: str, comment: str) -> Any:
    """Request a revision on a pending approval without fully rejecting it.

    The submitting agent will receive the comment and can resubmit.

    Args:
        approval_id: Approval UUID.
        comment: Required. Specific feedback describing what must change before approval.
    """
    if not comment.strip():
        return _err("A comment is required when requesting a revision.")
    return await _post(f"/approvals/{approval_id}/request-revision", {"comment": comment})


# ── COSTS & MONITORING ─────────────────────────────────────────────────────────

@mcp.tool()
async def get_cost_summary() -> Any:
    """Get aggregate token usage and spend for the active company this billing period.

    Returns total spend, remaining budget, and a per-agent cost breakdown.
    Use this to monitor AI spend and detect runaway agents.
    """
    return await _get(f"/companies/{COMPANY}/costs/summary")


@mcp.tool()
async def get_dashboard() -> Any:
    """Get a high-level health summary for the active company.

    Returns: agent count, open/in-progress/blocked issue counts, stale tasks,
    recent activity digest, and current-period cost totals.
    """
    return await _get(f"/companies/{COMPANY}/dashboard")


@mcp.tool()
async def list_activity(
    agent_id: str = "",
    limit: int = 20,
) -> Any:
    """Retrieve the audit trail of recent actions in the active company.

    Args:
        agent_id: Filter to a specific agent UUID. Leave empty for all agents.
        limit: Maximum number of entries to return (1–100). Default: 20.
    """
    params: dict[str, Any] = {"limit": max(1, min(limit, 100))}
    if agent_id:
        params["agentId"] = agent_id
    return await _get(f"/companies/{COMPANY}/activity", params)


# ── ENTRY POINT ────────────────────────────────────────────────────────────────

def main() -> None:
    """CLI entry point — invoked via `paperclip-mcp` or `python -m paperclip_mcp`."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="paperclip-mcp",
        description="MCP server for the Paperclip AI agent orchestration platform.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind address. Use 0.0.0.0 only in trusted local networks.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=9011,
        help="Bind port.",
    )
    parser.add_argument(
        "--transport",
        default="streamable-http",
        choices=["streamable-http", "sse", "stdio"],
        help=(
            "MCP transport protocol. "
            "'streamable-http' for Claude Code / mcp-proxy; "
            "'stdio' for Claude Desktop."
        ),
    )
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport=args.transport, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
