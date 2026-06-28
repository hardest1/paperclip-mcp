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


async def _put(path: str, body: dict[str, Any]) -> Any:
    return await _request("PUT", path, body=body)


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
    goal_id: str = "",
) -> Any:
    """Create a new issue (task) and optionally assign it to an agent.

    Use this to delegate work to agents, create subtasks, or track action items.

    Args:
        title: Short, imperative task title
               (e.g. "Search cheese suppliers in Barcelona").
        description: Full instructions or context for the agent
                     (Markdown supported).
        assignee_agent_id: UUID of the agent to assign.
        project_id: UUID of the project this issue belongs to.
        parent_issue_id: UUID of the parent issue (for subtasks).
        priority: urgent, high, medium, or low. Default: medium.
        goal_id: UUID of a goal to link this issue to.
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
    if goal_id:
        body["goalId"] = goal_id
    return await _post(f"/companies/{COMPANY}/issues", body)


@mcp.tool()
async def update_issue(
    issue_id: str,
    title: str = "",
    description: str = "",
    status: str = "",
    assignee_agent_id: str = "",
    priority: str = "",
    goal_id: str = "",
    project_id: str = "",
    parent_id: str = "",
    billing_code: str = "",
) -> Any:
    """Update an existing issue. Only fields you provide are changed.

    Args:
        issue_id: Issue UUID or identifier (e.g. "CY-42").
        title: New title.
        description: New description (Markdown).
        status: New status — todo, in_progress, blocked, done,
                or cancelled.
        assignee_agent_id: New agent UUID.
        priority: New priority — urgent, high, medium, or low.
        goal_id: UUID of a goal to link this issue to.
        project_id: UUID of the project to move this issue to.
        parent_id: UUID of a parent issue (for subtask grouping).
        billing_code: Billing code for cost tracking.
    """
    body: dict[str, Any] = {}
    if title:
        body["title"] = title
    if description:
        body["description"] = description
    if status:
        valid = {"todo", "in_progress", "blocked", "done", "cancelled"}
        if status not in valid:
            return _err(
                f"Invalid status '{status}'. "
                f"Allowed: {', '.join(sorted(valid))}."
            )
        body["status"] = status
    if assignee_agent_id:
        body["assigneeAgentId"] = assignee_agent_id
    if priority:
        valid_p = {"urgent", "high", "medium", "low"}
        if priority not in valid_p:
            return _err(
                f"Invalid priority '{priority}'. "
                f"Allowed: {', '.join(sorted(valid_p))}."
            )
        body["priority"] = priority
    if goal_id:
        body["goalId"] = goal_id
    if project_id:
        body["projectId"] = project_id
    if parent_id:
        body["parentId"] = parent_id
    if billing_code:
        body["billingCode"] = billing_code
    if not body:
        return _err(
            "No fields to update. Provide at least one of: "
            "title, description, status, assignee_agent_id, "
            "priority, goal_id, project_id, parent_id, "
            "billing_code."
        )
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

    Note: @-mentions (e.g. @AgentName) in comments trigger an immediate
    heartbeat for the mentioned agent.

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
async def list_issue_comments(issue_id: str) -> Any:
    """List all comments on an issue.

    Args:
        issue_id: Issue UUID or identifier.
    """
    return await _get(f"/issues/{issue_id}/comments")


@mcp.tool()
async def delete_issue(issue_id: str) -> Any:
    """Permanently delete an issue. This action cannot be undone.

    Args:
        issue_id: Issue UUID or identifier to delete.
    """
    return await _delete(f"/issues/{issue_id}")


# ── ISSUE INTERACTIONS ────────────────────────────────────────────────────────

_INTERACTION_KINDS = {"suggest_tasks", "ask_user_questions", "request_confirmation"}


@mcp.tool()
async def list_issue_interactions(issue_id: str) -> Any:
    """List structured interactions on an issue.

    Args:
        issue_id: Issue UUID or identifier.
    """
    return await _get(f"/issues/{issue_id}/interactions")


@mcp.tool()
async def create_issue_interaction(
    issue_id: str,
    kind: str,
    title: str,
    summary: str = "",
    idempotency_key: str = "",
    continuation_policy: str = "",
    payload: str = "",
) -> Any:
    """Create a structured interaction card on an issue.

    Interactions let agents present choices, questions, or confirmations
    to users through the Paperclip UI.

    Args:
        issue_id: Issue UUID or identifier.
        kind: Interaction kind — suggest_tasks,
              ask_user_questions, or request_confirmation.
        title: Card title shown in the UI.
        summary: Brief description of what the interaction asks.
        idempotency_key: Key to prevent duplicate interactions.
        continuation_policy: How the agent proceeds (e.g. "block").
        payload: JSON string with kind-specific data (e.g.
                 '{"prompt":"Ready?","acceptLabel":"Yes"}').
    """
    if kind not in _INTERACTION_KINDS:
        return _err(
            f"Invalid kind '{kind}'. "
            f"Allowed: {', '.join(sorted(_INTERACTION_KINDS))}."
        )
    body: dict[str, Any] = {"kind": kind, "title": title}
    if summary:
        body["summary"] = summary
    if idempotency_key:
        body["idempotencyKey"] = idempotency_key
    if continuation_policy:
        body["continuationPolicy"] = continuation_policy
    if payload:
        import json as _json

        try:
            body["payload"] = _json.loads(payload)
        except _json.JSONDecodeError:
            return _err("payload must be valid JSON.")
    return await _post(f"/issues/{issue_id}/interactions", body)


@mcp.tool()
async def accept_issue_interaction(
    issue_id: str,
    interaction_id: str,
) -> Any:
    """Accept an issue interaction (e.g. confirm a proposal).

    Args:
        issue_id: Issue UUID or identifier.
        interaction_id: Interaction UUID.
    """
    return await _post(
        f"/issues/{issue_id}/interactions/{interaction_id}/accept",
    )


@mcp.tool()
async def reject_issue_interaction(
    issue_id: str,
    interaction_id: str,
) -> Any:
    """Reject an issue interaction.

    Args:
        issue_id: Issue UUID or identifier.
        interaction_id: Interaction UUID.
    """
    return await _post(
        f"/issues/{issue_id}/interactions/{interaction_id}/reject",
    )


@mcp.tool()
async def respond_to_issue_interaction(
    issue_id: str,
    interaction_id: str,
    response: str = "",
) -> Any:
    """Respond to an issue interaction with structured data.

    Args:
        issue_id: Issue UUID or identifier.
        interaction_id: Interaction UUID.
        response: JSON string with the response data.
    """
    import json as _json

    try:
        parsed = _json.loads(response) if response else {}
    except _json.JSONDecodeError:
        return _err("response must be valid JSON.")
    return await _post(
        f"/issues/{issue_id}/interactions/{interaction_id}/respond",
        parsed,
    )


# ── ISSUE DOCUMENTS ──────────────────────────────────────────────────────────


@mcp.tool()
async def list_issue_documents(issue_id: str) -> Any:
    """List all documents attached to an issue.

    Args:
        issue_id: Issue UUID or identifier.
    """
    return await _get(f"/issues/{issue_id}/documents")


@mcp.tool()
async def get_issue_document(issue_id: str, key: str) -> Any:
    """Get a single issue document by its stable key.

    Args:
        issue_id: Issue UUID or identifier.
        key: Document key (e.g. "plan", "design", "notes").
    """
    return await _get(f"/issues/{issue_id}/documents/{key}")


@mcp.tool()
async def upsert_issue_document(
    issue_id: str,
    key: str,
    title: str,
    body: str,
    format: str = "markdown",
    base_revision_id: str = "",
) -> Any:
    """Create or update an issue document (revisioned text artifact).

    Omit base_revision_id when creating a new document. When updating, pass the
    current revision ID for optimistic concurrency — a stale ID returns 409.

    Args:
        issue_id: Issue UUID or identifier.
        key: Stable document key (e.g. "plan", "design", "notes").
        title: Human-readable document title.
        body: Document content.
        format: Content format (default "markdown").
        base_revision_id: Current revision ID for optimistic concurrency on updates.
    """
    payload: dict[str, Any] = {"title": title, "format": format, "body": body}
    if base_revision_id:
        payload["baseRevisionId"] = base_revision_id
    return await _put(f"/issues/{issue_id}/documents/{key}", payload)


@mcp.tool()
async def list_issue_document_revisions(issue_id: str, key: str) -> Any:
    """List revision history for an issue document.

    Args:
        issue_id: Issue UUID or identifier.
        key: Document key (e.g. "plan", "design", "notes").
    """
    return await _get(f"/issues/{issue_id}/documents/{key}/revisions")


@mcp.tool()
async def delete_issue_document(issue_id: str, key: str) -> Any:
    """Delete an issue document.

    Args:
        issue_id: Issue UUID or identifier.
        key: Document key to delete.
    """
    return await _delete(f"/issues/{issue_id}/documents/{key}")


# ── COMPANIES ─────────────────────────────────────────────────────────────────

@mcp.tool()
async def list_companies() -> Any:
    """List all companies accessible to the current API key."""
    return await _get("/companies")


@mcp.tool()
async def get_company(company_id: str) -> Any:
    """Get details for a specific company.

    Args:
        company_id: Company UUID.
    """
    return await _get(f"/companies/{company_id}")


@mcp.tool()
async def create_company(name: str, description: str = "") -> Any:
    """Create a new company.

    Args:
        name: Company name.
        description: Company description.
    """
    body: dict[str, Any] = {"name": name}
    if description:
        body["description"] = description
    return await _post("/companies", body)


@mcp.tool()
async def update_company(
    company_id: str,
    name: str = "",
    description: str = "",
    budget_monthly_cents: int = 0,
    logo_asset_id: str = "",
) -> Any:
    """Update an existing company. Only fields you provide are changed.

    Args:
        company_id: Company UUID.
        name: New company name.
        description: New description.
        budget_monthly_cents: Monthly budget cap in cents (0 to skip).
        logo_asset_id: Asset UUID for the company logo.
    """
    body: dict[str, Any] = {}
    if name:
        body["name"] = name
    if description:
        body["description"] = description
    if budget_monthly_cents:
        body["budgetMonthlyCents"] = budget_monthly_cents
    if logo_asset_id:
        body["logoAssetId"] = logo_asset_id
    if not body:
        return _err(
            "No fields to update. Provide at least one of: "
            "name, description, budget_monthly_cents, logo_asset_id."
        )
    return await _patch(f"/companies/{company_id}", body)


@mcp.tool()
async def archive_company(company_id: str) -> Any:
    """Archive a company. Archived companies can no longer run agents.

    Args:
        company_id: Company UUID to archive.
    """
    return await _post(f"/companies/{company_id}/archive")


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


@mcp.tool()
async def create_agent_api_key(agent_id: str) -> Any:
    """Create a long-lived API key for an agent.

    WARNING: The full key value is returned only once in this response.
    Store it immediately — it cannot be retrieved again.

    Args:
        agent_id: UUID of the agent.
    """
    return await _post(f"/agents/{agent_id}/keys")


@mcp.tool()
async def list_agent_config_revisions(agent_id: str) -> Any:
    """List configuration change history for an agent.

    Args:
        agent_id: UUID of the agent.
    """
    return await _get(f"/agents/{agent_id}/config-revisions")


@mcp.tool()
async def rollback_agent_config(
    agent_id: str,
    revision_id: str,
) -> Any:
    """Roll back an agent's configuration to a previous revision.

    Args:
        agent_id: UUID of the agent.
        revision_id: UUID of the config revision to restore.
    """
    return await _post(
        f"/agents/{agent_id}/config-revisions/{revision_id}/rollback",
    )


@mcp.tool()
async def get_org_chart() -> Any:
    """Get the full organizational chart for the active company.

    Returns the agent hierarchy tree showing reporting relationships.
    """
    return await _get(f"/companies/{COMPANY}/org")


@mcp.tool()
async def list_adapter_models(adapter_type: str) -> Any:
    """List available models for an adapter type.

    Args:
        adapter_type: Adapter type (e.g. "claude", "openai",
                      "codex_local", "opencode_local").
    """
    return await _get(
        f"/companies/{COMPANY}/adapters/{adapter_type}/models",
    )


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


# ── ROUTINE TRIGGERS ──────────────────────────────────────────────────────────

_TRIGGER_KINDS = {"schedule", "webhook", "api"}


@mcp.tool()
async def add_routine_trigger(
    routine_id: str,
    kind: str,
    cron_expression: str = "",
    timezone: str = "",
    signing_mode: str = "",
    replay_window_sec: int = 0,
) -> Any:
    """Add a trigger to a routine.

    Three trigger kinds are supported:
    - schedule: fires on a cron schedule
    - webhook: fires when an external webhook is received
    - api: fires via the Paperclip API

    Args:
        routine_id: UUID of the routine to add a trigger to.
        kind: Trigger kind — schedule, webhook, or api.
        cron_expression: Cron expression (schedule triggers only).
        timezone: IANA timezone for the cron schedule
                  (e.g. "Europe/Berlin"). Schedule triggers only.
        signing_mode: Signing mode for webhook triggers
                      (e.g. "hmac_sha256").
        replay_window_sec: Replay protection window in seconds
                           (30–86400). Webhook triggers only.
    """
    if kind not in _TRIGGER_KINDS:
        return _err(
            f"Invalid trigger kind '{kind}'. "
            f"Allowed: {', '.join(sorted(_TRIGGER_KINDS))}."
        )
    if replay_window_sec and not (30 <= replay_window_sec <= 86400):
        return _err(
            "replay_window_sec must be between 30 and 86400."
        )
    body: dict[str, Any] = {"kind": kind}
    if cron_expression:
        body["cronExpression"] = cron_expression
    if timezone:
        body["timezone"] = timezone
    if signing_mode:
        body["signingMode"] = signing_mode
    if replay_window_sec:
        body["replayWindowSec"] = replay_window_sec
    return await _post(f"/routines/{routine_id}/triggers", body)


@mcp.tool()
async def update_routine_trigger(
    trigger_id: str,
    enabled: bool | None = None,
    cron_expression: str = "",
    timezone: str = "",
    signing_mode: str = "",
    replay_window_sec: int = 0,
) -> Any:
    """Update an existing routine trigger.

    Args:
        trigger_id: Trigger UUID.
        enabled: Set to false to disable the trigger without deleting it.
        cron_expression: New cron expression (schedule triggers).
        timezone: New timezone (schedule triggers).
        signing_mode: New signing mode (webhook triggers).
        replay_window_sec: New replay window in seconds (30–86400).
    """
    if replay_window_sec and not (30 <= replay_window_sec <= 86400):
        return _err("replay_window_sec must be between 30 and 86400.")
    body: dict[str, Any] = {}
    if enabled is not None:
        body["enabled"] = enabled
    if cron_expression:
        body["cronExpression"] = cron_expression
    if timezone:
        body["timezone"] = timezone
    if signing_mode:
        body["signingMode"] = signing_mode
    if replay_window_sec:
        body["replayWindowSec"] = replay_window_sec
    if not body:
        return _err(
            "No fields to update. Provide at least one of: "
            "enabled, cron_expression, timezone, signing_mode, "
            "replay_window_sec."
        )
    return await _patch(f"/routine-triggers/{trigger_id}", body)


@mcp.tool()
async def delete_routine_trigger(trigger_id: str) -> Any:
    """Delete a routine trigger.

    Args:
        trigger_id: Trigger UUID to delete.
    """
    return await _delete(f"/routine-triggers/{trigger_id}")


@mcp.tool()
async def rotate_trigger_secret(trigger_id: str) -> Any:
    """Rotate the signing secret for a webhook trigger.

    Generates a new secret and invalidates the previous one.
    The new secret is returned in the response — store it
    immediately as it cannot be retrieved again.

    Args:
        trigger_id: UUID of the webhook trigger.
    """
    return await _post(f"/routine-triggers/{trigger_id}/rotate-secret")


# ── ROUTINE RUNS & REVISIONS ─────────────────────────────────────────────────

@mcp.tool()
async def run_routine(
    routine_id: str,
    trigger_id: str = "",
    payload: str = "",
    idempotency_key: str = "",
) -> Any:
    """Manually trigger a routine run.

    The routine's concurrency policy still applies — if the routine is
    already running and the policy is skip_if_active, this call may be
    rejected.

    Args:
        routine_id: UUID of the routine to run.
        trigger_id: Optional trigger UUID to associate with this run.
        payload: Optional JSON payload to pass to the routine
                 (e.g. '{"key":"value"}').
        idempotency_key: Optional key to prevent duplicate runs.
    """
    body: dict[str, Any] = {"source": "manual"}
    if trigger_id:
        body["triggerId"] = trigger_id
    if payload:
        import json as _json

        try:
            body["payload"] = _json.loads(payload)
        except _json.JSONDecodeError:
            return _err("payload must be valid JSON.")
    if idempotency_key:
        body["idempotencyKey"] = idempotency_key
    return await _post(f"/routines/{routine_id}/run", body)


@mcp.tool()
async def list_routine_runs(
    routine_id: str,
    limit: int = 50,
) -> Any:
    """List recent runs for a routine.

    Args:
        routine_id: UUID of the routine.
        limit: Maximum number of runs to return (1–200). Default: 50.
    """
    return await _get(
        f"/routines/{routine_id}/runs",
        {"limit": max(1, min(limit, 200))},
    )


@mcp.tool()
async def list_routine_revisions(routine_id: str) -> Any:
    """List definition revisions for a routine, newest first.

    Revisions are append-only — every update creates a new revision.

    Args:
        routine_id: UUID of the routine.
    """
    return await _get(f"/routines/{routine_id}/revisions")


@mcp.tool()
async def restore_routine_revision(
    routine_id: str,
    revision_id: str,
) -> Any:
    """Restore a routine to a previous revision.

    Creates a new latest revision copied from the selected historical
    revision.

    Args:
        routine_id: UUID of the routine.
        revision_id: UUID of the revision to restore.
    """
    return await _post(f"/routines/{routine_id}/revisions/{revision_id}/restore")


# ── PROJECTS ──────────────────────────────────────────────────────────────────

@mcp.tool()
async def list_projects() -> Any:
    """List all projects in the active company."""
    return await _get(f"/companies/{COMPANY}/projects")


@mcp.tool()
async def get_project(project_id: str) -> Any:
    """Get full details of a project including its workspaces.

    Args:
        project_id: Project UUID.
    """
    return await _get(f"/projects/{project_id}")


@mcp.tool()
async def create_project(
    name: str,
    description: str = "",
    goal_ids: str = "",
    status: str = "",
    workspace_name: str = "",
    workspace_cwd: str = "",
    workspace_repo_url: str = "",
    workspace_repo_ref: str = "",
    workspace_is_primary: bool = False,
) -> Any:
    """Create a new project, optionally seeding an initial workspace.

    Args:
        name: Project name.
        description: Project description (Markdown).
        goal_ids: Comma-separated goal UUIDs to link to.
        status: Project status (e.g. "active", "completed").
        workspace_name: Name for the initial workspace (seeds a
                        workspace if provided alongside cwd or repo_url).
        workspace_cwd: Local directory path for the workspace.
        workspace_repo_url: Git repository URL for the workspace.
        workspace_repo_ref: Git ref (branch/tag) for the workspace.
        workspace_is_primary: Mark the initial workspace as primary.
    """
    body: dict[str, Any] = {"name": name}
    if description:
        body["description"] = description
    if goal_ids:
        body["goalIds"] = [g.strip() for g in goal_ids.split(",") if g.strip()]
    if status:
        body["status"] = status
    if workspace_name or workspace_cwd or workspace_repo_url:
        ws: dict[str, Any] = {}
        if workspace_name:
            ws["name"] = workspace_name
        if workspace_cwd:
            ws["cwd"] = workspace_cwd
        if workspace_repo_url:
            ws["repoUrl"] = workspace_repo_url
        if workspace_repo_ref:
            ws["repoRef"] = workspace_repo_ref
        if workspace_is_primary:
            ws["isPrimary"] = True
        body["workspace"] = ws
    return await _post(f"/companies/{COMPANY}/projects", body)


@mcp.tool()
async def update_project(
    project_id: str,
    name: str = "",
    description: str = "",
    status: str = "",
) -> Any:
    """Update an existing project. Only fields you provide are changed.

    Args:
        project_id: Project UUID.
        name: New project name.
        description: New description (Markdown).
        status: New status (e.g. "active", "completed").
    """
    body: dict[str, Any] = {}
    if name:
        body["name"] = name
    if description:
        body["description"] = description
    if status:
        body["status"] = status
    if not body:
        return _err(
            "No fields to update. Provide at least one of: "
            "name, description, status."
        )
    return await _patch(f"/projects/{project_id}", body)


# ── PROJECT WORKSPACES ────────────────────────────────────────────────────────

@mcp.tool()
async def list_project_workspaces(project_id: str) -> Any:
    """List workspaces for a project.

    Args:
        project_id: Project UUID.
    """
    return await _get(f"/projects/{project_id}/workspaces")


@mcp.tool()
async def add_project_workspace(
    project_id: str,
    name: str,
    cwd: str = "",
    repo_url: str = "",
    repo_ref: str = "",
    is_primary: bool = False,
) -> Any:
    """Add a workspace to a project.

    At least one of cwd or repo_url is required.

    Args:
        project_id: Project UUID.
        name: Workspace name.
        cwd: Local directory path.
        repo_url: Git repository URL.
        repo_ref: Git ref (branch/tag).
        is_primary: Mark as the primary workspace.
    """
    body: dict[str, Any] = {"name": name}
    if cwd:
        body["cwd"] = cwd
    if repo_url:
        body["repoUrl"] = repo_url
    if repo_ref:
        body["repoRef"] = repo_ref
    if is_primary:
        body["isPrimary"] = True
    return await _post(f"/projects/{project_id}/workspaces", body)


@mcp.tool()
async def update_project_workspace(
    project_id: str,
    workspace_id: str,
    name: str = "",
    cwd: str = "",
    repo_url: str = "",
    repo_ref: str = "",
    is_primary: bool | None = None,
) -> Any:
    """Update a project workspace. Only fields you provide are changed.

    Args:
        project_id: Project UUID.
        workspace_id: Workspace UUID.
        name: New workspace name.
        cwd: New local directory path.
        repo_url: New Git repository URL.
        repo_ref: New Git ref (branch/tag).
        is_primary: Set as primary workspace.
    """
    body: dict[str, Any] = {}
    if name:
        body["name"] = name
    if cwd:
        body["cwd"] = cwd
    if repo_url:
        body["repoUrl"] = repo_url
    if repo_ref:
        body["repoRef"] = repo_ref
    if is_primary is not None:
        body["isPrimary"] = is_primary
    if not body:
        return _err(
            "No fields to update. Provide at least one of: "
            "name, cwd, repo_url, repo_ref, is_primary."
        )
    return await _patch(f"/projects/{project_id}/workspaces/{workspace_id}", body)


@mcp.tool()
async def delete_project_workspace(
    project_id: str,
    workspace_id: str,
) -> Any:
    """Delete a workspace from a project.

    Args:
        project_id: Project UUID.
        workspace_id: Workspace UUID to delete.
    """
    return await _delete(f"/projects/{project_id}/workspaces/{workspace_id}")


# ── GOALS ──────────────────────────────────────────────────────────────────────

_GOAL_LEVELS = {"company", "team", "agent"}
_GOAL_STATUSES = {"planned", "active", "achieved", "cancelled"}


@mcp.tool()
async def list_goals() -> Any:
    """List all strategic goals for the active company."""
    return await _get(f"/companies/{COMPANY}/goals")


@mcp.tool()
async def get_goal(goal_id: str) -> Any:
    """Get full details of a single goal.

    Args:
        goal_id: Goal UUID.
    """
    return await _get(f"/goals/{goal_id}")


@mcp.tool()
async def create_goal(
    title: str,
    description: str = "",
    level: str = "",
    status: str = "",
) -> Any:
    """Create a new strategic goal for the active company.

    Goals form a hierarchy: company → team → agent-level.

    Args:
        title: Goal title
               (e.g. "Reach 300 packs/month in sales by June 2026").
        description: Extended context, success criteria, and
                     constraints (Markdown supported).
        level: Goal level — company, team, or agent.
        status: Goal status — planned, active, achieved,
                or cancelled.
    """
    if level and level not in _GOAL_LEVELS:
        return _err(
            f"Invalid level '{level}'. "
            f"Allowed: {', '.join(sorted(_GOAL_LEVELS))}."
        )
    if status and status not in _GOAL_STATUSES:
        return _err(
            f"Invalid status '{status}'. "
            f"Allowed: {', '.join(sorted(_GOAL_STATUSES))}."
        )
    body: dict[str, Any] = {"title": title}
    if description:
        body["description"] = description
    if level:
        body["level"] = level
    if status:
        body["status"] = status
    return await _post(f"/companies/{COMPANY}/goals", body)


@mcp.tool()
async def update_goal(
    goal_id: str,
    title: str = "",
    description: str = "",
    status: str = "",
) -> Any:
    """Update an existing goal.

    Args:
        goal_id: Goal UUID.
        title: New title.
        description: New description.
        status: New status — planned, active, achieved,
                or cancelled.
    """
    if status and status not in _GOAL_STATUSES:
        return _err(
            f"Invalid status '{status}'. "
            f"Allowed: {', '.join(sorted(_GOAL_STATUSES))}."
        )
    body: dict[str, Any] = {}
    if title:
        body["title"] = title
    if description:
        body["description"] = description
    if status:
        body["status"] = status
    if not body:
        return _err(
            "No fields to update. Provide at least one of: "
            "title, description, status."
        )
    return await _patch(f"/goals/{goal_id}", body)


# ── SECRETS ───────────────────────────────────────────────────────────────────

@mcp.tool()
async def list_secrets() -> Any:
    """List all secrets for the active company (metadata only).

    Returns secret names, IDs, and provider info. Secret values are
    never exposed through this tool.
    """
    return await _get(f"/companies/{COMPANY}/secrets")


@mcp.tool()
async def create_secret(
    name: str,
    value: str = "",
    provider: str = "",
    managed_mode: str = "",
    external_ref: str = "",
    provider_version_ref: str = "",
    provider_config_id: str = "",
) -> Any:
    """Create a new encrypted secret.

    Two modes are supported:
    - Basic: provide name + value (encrypted at rest)
    - External reference: provide name + provider + managed_mode +
      external_ref for secrets managed in an external vault

    Args:
        name: Secret name (e.g. "DATABASE_URL").
        value: Secret value (basic mode). Encrypted at rest.
        provider: Provider backend (e.g. "aws_secrets_manager").
        managed_mode: Set to "external_reference" for vault-managed
                      secrets.
        external_ref: External secret reference (e.g. ARN).
        provider_version_ref: Version reference in the external vault.
        provider_config_id: UUID of a provider vault config to pin to.
    """
    body: dict[str, Any] = {"name": name}
    if value:
        body["value"] = value
    if provider:
        body["provider"] = provider
    if managed_mode:
        body["managedMode"] = managed_mode
    if external_ref:
        body["externalRef"] = external_ref
    if provider_version_ref:
        body["providerVersionRef"] = provider_version_ref
    if provider_config_id:
        body["providerConfigId"] = provider_config_id
    return await _post(f"/companies/{COMPANY}/secrets", body)


@mcp.tool()
async def rotate_secret(
    secret_id: str,
    value: str,
    provider_config_id: str = "",
) -> Any:
    """Rotate a secret to a new value.

    Agents configured with version: "latest" will receive the new
    value on their next heartbeat.

    Args:
        secret_id: Secret UUID.
        value: New secret value.
        provider_config_id: UUID of a provider vault config (optional).
    """
    body: dict[str, Any] = {"value": value}
    if provider_config_id:
        body["providerConfigId"] = provider_config_id
    return await _post(f"/secrets/{secret_id}/rotate", body)


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
async def get_approval(approval_id: str) -> Any:
    """Get full details of an approval request.

    Args:
        approval_id: Approval UUID.
    """
    return await _get(f"/approvals/{approval_id}")


@mcp.tool()
async def approve(approval_id: str, comment: str = "") -> Any:
    """Approve a pending approval request.

    Args:
        approval_id: Approval UUID.
        comment: Optional decision note (e.g. conditions, context).
    """
    body: dict[str, Any] = {}
    if comment:
        body["decisionNote"] = comment
    return await _post(f"/approvals/{approval_id}/approve", body)


@mcp.tool()
async def reject(approval_id: str, comment: str = "") -> Any:
    """Reject a pending approval request.

    Args:
        approval_id: Approval UUID.
        comment: Reason for rejection — strongly recommended so the
                 agent understands why.
    """
    body: dict[str, Any] = {}
    if comment:
        body["decisionNote"] = comment
    return await _post(f"/approvals/{approval_id}/reject", body)


@mcp.tool()
async def request_approval_revision(approval_id: str, comment: str) -> Any:
    """Request a revision on a pending approval without fully rejecting it.

    The submitting agent will receive the comment and can resubmit.

    Args:
        approval_id: Approval UUID.
        comment: Required. Specific feedback describing what must
                 change before approval.
    """
    if not comment.strip():
        return _err("A comment is required when requesting a revision.")
    return await _post(
        f"/approvals/{approval_id}/request-revision",
        {"comment": comment},
    )


@mcp.tool()
async def create_approval_request(
    approval_type: str,
    requested_by_agent_id: str,
    payload: str = "",
) -> Any:
    """Create a new approval request.

    Args:
        approval_type: Approval type (e.g. "budget_increase",
                       "hire_agent").
        requested_by_agent_id: UUID of the agent requesting approval.
        payload: JSON string with type-specific data
                 (e.g. '{"amount":5000}').
    """
    body: dict[str, Any] = {
        "type": approval_type,
        "requestedByAgentId": requested_by_agent_id,
    }
    if payload:
        import json as _json

        try:
            body["payload"] = _json.loads(payload)
        except _json.JSONDecodeError:
            return _err("payload must be valid JSON.")
    return await _post(f"/companies/{COMPANY}/approvals", body)


@mcp.tool()
async def create_hire_request(
    name: str,
    role: str,
    budget_monthly_cents: int = 0,
    reports_to: str = "",
    capabilities: str = "",
) -> Any:
    """Create an agent hire request (draft agent + hire approval).

    This creates a draft agent and a linked hire_agent approval that
    must be approved before the agent becomes active.

    Args:
        name: Name for the new agent.
        role: Role description (e.g. "researcher", "engineer").
        budget_monthly_cents: Monthly budget cap in cents.
        reports_to: UUID of the agent this one reports to.
        capabilities: Comma-separated capability tags.
    """
    body: dict[str, Any] = {"name": name, "role": role}
    if budget_monthly_cents:
        body["budgetMonthlyCents"] = budget_monthly_cents
    if reports_to:
        body["reportsTo"] = reports_to
    if capabilities:
        body["capabilities"] = capabilities
    return await _post(f"/companies/{COMPANY}/agent-hires", body)


@mcp.tool()
async def resubmit_approval(approval_id: str, payload: str) -> Any:
    """Resubmit an approval after revision was requested.

    Part of the revision_requested → resubmitted → pending flow.

    Args:
        approval_id: Approval UUID.
        payload: JSON string with the updated configuration.
    """
    import json as _json

    try:
        parsed = _json.loads(payload)
    except _json.JSONDecodeError:
        return _err("payload must be valid JSON.")
    return await _post(
        f"/approvals/{approval_id}/resubmit",
        {"payload": parsed},
    )


@mcp.tool()
async def list_approval_issues(approval_id: str) -> Any:
    """List issues linked to an approval.

    Args:
        approval_id: Approval UUID.
    """
    return await _get(f"/approvals/{approval_id}/issues")


@mcp.tool()
async def list_approval_comments(approval_id: str) -> Any:
    """List comments on an approval.

    Args:
        approval_id: Approval UUID.
    """
    return await _get(f"/approvals/{approval_id}/comments")


@mcp.tool()
async def comment_on_approval(approval_id: str, body: str) -> Any:
    """Add a comment to an approval request.

    Args:
        approval_id: Approval UUID.
        body: Comment text (Markdown supported).
    """
    return await _post(
        f"/approvals/{approval_id}/comments",
        {"body": body},
    )


# ── COSTS & MONITORING ─────────────────────────────────────────────────────────

@mcp.tool()
async def get_cost_summary() -> Any:
    """Get aggregate token usage and spend for the active company this billing period.

    Returns total spend, remaining budget, and a per-agent cost breakdown.
    Use this to monitor AI spend and detect runaway agents.
    """
    return await _get(f"/companies/{COMPANY}/costs/summary")


@mcp.tool()
async def get_costs_by_agent() -> Any:
    """Get per-agent cost breakdown for the current billing period.

    Returns a list of agents with their token usage and spend in cents.
    """
    return await _get(f"/companies/{COMPANY}/costs/by-agent")


@mcp.tool()
async def get_costs_by_project() -> Any:
    """Get per-project cost breakdown for the current billing period.

    Returns a list of projects with their token usage and spend in cents.
    """
    return await _get(f"/companies/{COMPANY}/costs/by-project")


@mcp.tool()
async def report_cost_event(
    agent_id: str,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_cents: int,
) -> Any:
    """Report a manual cost event for token usage tracking.

    Typically auto-reported by adapters, but useful for manual or
    external-model tracking.

    Args:
        agent_id: Agent UUID that incurred the cost.
        provider: LLM provider name (e.g. "openai", "anthropic").
        model: Model identifier (e.g. "gpt-4o", "claude-sonnet-4-20250514").
        input_tokens: Number of input tokens consumed.
        output_tokens: Number of output tokens consumed.
        cost_cents: Total cost in cents.
    """
    return await _post(
        f"/companies/{COMPANY}/cost-events",
        {
            "agentId": agent_id,
            "provider": provider,
            "model": model,
            "inputTokens": input_tokens,
            "outputTokens": output_tokens,
            "costCents": cost_cents,
        },
    )


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
