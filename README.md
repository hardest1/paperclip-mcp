# paperclip-mcp

MCP server for the [Paperclip](https://github.com/paperclipai/paperclip) AI agent orchestration platform.

Exposes Paperclip's REST API as [Model Context Protocol](https://modelcontextprotocol.io) tools, so any MCP-compatible AI assistant (Claude, etc.) can manage issues, agents, routines, projects, goals, approvals, secrets, and costs through natural language.

---

## Features (90 tools)

| Category | Tools |
|---|---|
| **Issues** | `list_issues` · `get_issue` · `create_issue` · `update_issue` · `checkout_issue` · `release_issue` · `comment_on_issue` · `list_issue_comments` · `delete_issue` |
| **Issue Interactions** | `list_issue_interactions` · `create_issue_interaction` · `accept_issue_interaction` · `reject_issue_interaction` · `respond_to_issue_interaction` |
| **Issue Documents** | `list_issue_documents` · `get_issue_document` · `upsert_issue_document` · `list_issue_document_revisions` · `delete_issue_document` |
| **Issue Attachments** | `list_issue_attachments` · `upload_issue_attachment` · `download_attachment` · `delete_attachment` |
| **Active Company** | `get_active_company` · `set_active_company` |
| **Companies** | `list_companies` · `get_company` · `create_company` · `update_company` · `archive_company` |
| **Agents** | `list_agents` · `get_agent` · `create_agent` · `update_agent` · `pause_agent` · `resume_agent` · `clear_agent_error` · `terminate_agent` · `invoke_agent_heartbeat` |
| **Agent Config** | `create_agent_api_key` · `list_agent_config_revisions` · `rollback_agent_config` · `get_org_chart` · `list_adapter_models` |
| **Routines** | `list_routines` · `get_routine` · `create_routine` · `update_routine` |
| **Routine Triggers** | `add_routine_trigger` · `update_routine_trigger` · `delete_routine_trigger` · `rotate_trigger_secret` |
| **Routine Runs** | `run_routine` · `list_routine_runs` · `list_routine_revisions` · `restore_routine_revision` |
| **Projects** | `list_projects` · `get_project` · `create_project` · `update_project` |
| **Project Workspaces** | `list_project_workspaces` · `add_project_workspace` · `update_project_workspace` · `delete_project_workspace` |
| **Goals** | `list_goals` · `get_goal` · `create_goal` · `update_goal` |
| **Secrets** | `list_secrets` · `create_secret` · `rotate_secret` |
| **Secret Providers** | `list_secret_provider_configs` · `get_secret_provider_config` · `create_secret_provider_config` · `update_secret_provider_config` · `disable_secret_provider_config` · `set_default_secret_provider_config` · `check_secret_provider_health` · `get_secret_providers_health` |
| **Approvals** | `list_approvals` · `get_approval` · `approve` · `reject` · `request_approval_revision` · `create_approval_request` · `create_hire_request` · `resubmit_approval` · `list_approval_issues` · `list_approval_comments` · `comment_on_approval` |
| **Costs & Monitoring** | `get_cost_summary` · `get_costs_by_agent` · `get_costs_by_project` · `report_cost_event` · `get_dashboard` · `list_activity` |

---

## Requirements

- Python 3.10+
- A running [Paperclip](https://github.com/paperclipai/paperclip) instance
- An Agent API key (generated in Paperclip UI → Settings → API Keys)

---

## Installation

### Option A — pip / uv (recommended)

```bash
# Clone the repo
git clone https://github.com/wizarck/paperclip-mcp
cd paperclip-mcp

# Install (editable for local use, or drop -e for production)
pip install -e .
# or
uv pip install -e .
```

### Option B — Run directly without installing

```bash
pip install fastmcp httpx python-dotenv
python src/paperclip_mcp/server.py
```

---

## Configuration

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

```dotenv
PAPERCLIP_BASE_URL=http://localhost:3100/api   # default, change if needed
PAPERCLIP_API_KEY=your_api_key_here
# PAPERCLIP_COMPANY_ID=your_company_uuid_here  # optional — see below
```

> **Security**: Never commit `.env` to version control. It is listed in `.gitignore`.

**Where to find these values:**
- `PAPERCLIP_API_KEY` — Paperclip UI → Settings → API Keys → New Key
- `PAPERCLIP_COMPANY_ID` — visible in the URL when viewing your company: `/companies/{uuid}`

**Multi-company mode**: If your API key can access multiple companies (e.g. a board key), omit `PAPERCLIP_COMPANY_ID`. Then use `set_active_company` to switch between companies during a conversation, or pass `company_id` to individual tools.

---

## Usage

### Start the server

```bash
# HTTP (for Claude Code / mcp-proxy) — default port 9011
paperclip-mcp

# Custom port
paperclip-mcp --port 9012

# stdio transport (for Claude Desktop)
paperclip-mcp --transport stdio

# All options
paperclip-mcp --help
```

### Register with Claude Code

```bash
# HTTP transport (persistent — survives Claude restarts)
claude mcp add paperclip --transport http http://localhost:9011/mcp

# stdio transport (Claude Desktop — add to claude_desktop_config.json)
```

#### Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "paperclip": {
      "command": "paperclip-mcp",
      "args": ["--transport", "stdio"],
      "env": {
        "PAPERCLIP_API_KEY": "your_api_key"
      }
    }
  }
}
```

---

## Example interactions

Once registered, you can ask your AI assistant:

```
"What tasks does the Purchasing agent have open?"
→ calls list_issues(assignee_agent_id="...", status="todo,in_progress")

"Create a task for the CEO agent to search for new cheese suppliers in Barcelona"
→ calls create_issue(title="Search cheese suppliers in Barcelona", assignee_agent_id="...")

"Approve the pending hire request"
→ calls list_approvals(status="pending") + approve(approval_id="...")

"How much have we spent on tokens this month, broken down by agent?"
→ calls get_costs_by_agent()

"Pause the Marketing agent and check its error state"
→ calls pause_agent(agent_id="...") + get_agent(agent_id="...")

"Create a daily routine that runs at 9am"
→ calls create_routine(...) + add_routine_trigger(kind="schedule", cron="0 9 * * *", ...)

"Show me the revision history of the plan document on issue #42"
→ calls list_issue_document_revisions(issue_id="...", key="plan")

"What projects are active and how are their workspaces configured?"
→ calls list_projects() + list_project_workspaces(project_id="...")

"Check the health of all secret provider vaults"
→ calls get_secret_providers_health()

"Wake up the Administration agent now"
→ calls invoke_agent_heartbeat(agent_id="...")
```

---

## Auto-start with the MCP stack

Add to your stack startup script:

```bash
# Check if already running
curl -s --max-time 1 http://localhost:9011/mcp > /dev/null 2>&1 || \
  nohup paperclip-mcp > /tmp/paperclip-mcp.log 2>&1 &
```

---

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Lint
ruff check src/
ruff format src/

# Type check
mypy src/

# Tests
pytest
```

---

## Architecture notes

- **Who should use this MCP**: Human operators managing agents via Claude Code or Claude Desktop.
- **Do agents need this MCP?**: No — Paperclip agents already interact with the REST API directly via HTTP in their HEARTBEAT protocol. This MCP is for the human operator layer.
- **Hermes agents**: If you switch to [Hermes](https://github.com/NousResearch/hermes-paperclip-adapter), this MCP is automatically available since Hermes supports MCP natively.
- **Transport choice**: Use `streamable-http` for Claude Code and mcp-proxy integrations. Use `stdio` for Claude Desktop.
- **Security**: The server binds to `127.0.0.1` by default (localhost only). Do not expose it publicly — it carries your Paperclip API key.

---

## License

MIT — see [LICENSE](LICENSE).
