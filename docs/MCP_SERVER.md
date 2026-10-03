# StructAI MCP server

`app/mcp/server.py` exposes StructAI's capabilities as an [MCP](https://modelcontextprotocol.io)
server, so an MCP client (Claude Desktop, Claude Code, or any other MCP host) can ask
structured questions, manage projects/chats/files, and search —
all against the real backend, through the same `app/services/*` functions the HTTP API uses.

It is a second transport onto the same application, not a separate service: every tool
call opens its own short-lived DB session and runs behind the same auth, rate limit, and
daily quota the HTTP routes enforce. No business logic lives in `app/mcp/server.py` itself.

## 1. Issue credentials

The MCP server acts as one specific StructAI account, authenticated with a real JWT
access/refresh token pair (not a separate API-key system). Issue one with:

```bash
# First time (creates the account too):
.venv/bin/python3 scripts/mcp_issue_token.py --email you@example.com --password yourpassword --register

# Account already exists:
.venv/bin/python3 scripts/mcp_issue_token.py --email you@example.com --password yourpassword
```

This prints two lines — paste them into `.env`:

```
MCP_ACCESS_TOKEN=eyJ...
MCP_REFRESH_TOKEN=eyJ...
```

Access tokens are short-lived (`JWT_ACCESS_EXPIRE_MIN`, 15 min by default). The MCP server
refreshes automatically in-process using `MCP_REFRESH_TOKEN` when the access token expires.
Refresh tokens are one-time use and rotate on every refresh — the refreshed pair only lives
in that process's memory, so if the MCP server process restarts after a refresh has already
happened, the refresh token saved in `.env` may be stale. Re-run `scripts/mcp_issue_token.py`
to issue a fresh pair if the server ever reports an auth failure.

## 2. Configure your MCP client

### Claude Desktop

Add to `claude_desktop_config.json` (Settings → Developer → Edit Config):

```json
{
  "mcpServers": {
    "structai": {
      "command": "/absolute/path/to/assignment2/.venv/bin/python3",
      "args": ["-m", "app.mcp.server"],
      "cwd": "/absolute/path/to/assignment2",
      "env": {
        "MCP_ACCESS_TOKEN": "eyJ...",
        "MCP_REFRESH_TOKEN": "eyJ...",
        "DATABASE_URL": "sqlite+aiosqlite:///./data/structai.db",
        "JWT_SECRET": "<same value as your .env>"
      }
    }
  }
}
```

Restart Claude Desktop. StructAI's tools then show up alongside any other configured MCP server.

### Claude Code

```bash
claude mcp add structai \
  -e MCP_ACCESS_TOKEN=eyJ... \
  -e MCP_REFRESH_TOKEN=eyJ... \
  -e DATABASE_URL=sqlite+aiosqlite:///./data/structai.db \
  -e JWT_SECRET=<same value as your .env> \
  -- /absolute/path/to/assignment2/.venv/bin/python3 -m app.mcp.server
```

Claude Code inherits your shell environment, so if `.env` is already loaded (e.g. via
`direnv`, or the backend was started from a shell that sourced it), the `-e` flags above can
be omitted.

### Smoke-testing without a GUI client

```bash
make mcp
# or: python3 -m app.mcp.server
```

Runs the server on stdio. [MCP Inspector](https://github.com/modelcontextprotocol/inspector)
(`npx @modelcontextprotocol/inspector python3 -m app.mcp.server`) is the easiest way to call
tools interactively without a full chat client.

## 3. Tools

All tools act on whichever account `MCP_ACCESS_TOKEN` belongs to; project/chat/file data and
quota usage are scoped to that account, exactly as they would be over the HTTP API.

| Tool | Purpose |
|---|---|
| `ask_structured(prompt, fields, tier="fast")` | Ask a question, get back JSON guaranteed to match `fields`. Same guardrails (injection screen, PII redaction, rate limit, daily quota) and retry-with-corrective-feedback loop as `POST /structured/answer`. |
| `validate_schema(fields)` | Check a field schema is well-formed; returns its JSON Schema. |
| `list_projects()` | List the account's projects, newest first. |
| `create_project(name)` | Create a project. |
| `list_chats(project_id=None)` | List chats, optionally filtered to a project. |
| `create_chat(title, project_id=None)` | Create a chat. |
| `list_messages(chat_id)` | List a chat's messages in order. |
| `send_message(chat_id, content, role="user")` | Append a message (persists only — does not call a model). |
| `list_files(chat_id=None)` | List stored file attachments, optionally filtered to a chat. |
| `get_file(file_id)` | Get one file's metadata. |
| `search(query)` | Search the account's own chat titles and message content. |
| `get_usage()` | Today's request-quota usage. |

`fields` uses StructAI's schema format directly — the same shape `POST /structured/answer`
takes — e.g.:

```json
[
  {"name": "capital", "type": "string"},
  {"name": "population", "type": "integer", "required": false}
]
```

Allowed types: `string`, `integer`, `number`, `boolean`, `string_list`, `integer_list`.

## 4. Resources

| URI | Content |
|---|---|
| `structai://usage` | Today's quota usage, as JSON. |
| `structai://projects` | The account's projects, as a JSON array. |

## 5. Error handling

A failing tool call (auth failure, guardrail block, exhausted retries, not-found, etc.)
surfaces to the MCP client as a tool error with the same message the HTTP API's JSON error
body would carry — the underlying `AppError` subclass (`GuardrailError`, `NotFoundError`,
`RateLimitError`, ...) is simply raised from the tool function and wrapped by the MCP SDK.

## 6. Known limitations

- Tools return plain JSON-serializable dicts rather than using the MCP SDK's binary
  `Image`/`Audio` content helpers — simpler and more testable, at the cost of a client not
  getting file content rendered inline; fetch it over the HTTP API
  (`GET /files/{id}/content`) to view it.
- If both the configured access token and refresh token are invalid/expired/revoked at the
  same time, every tool call fails until `scripts/mcp_issue_token.py` is re-run and `.env`
  (or your MCP client's config) is updated with a fresh pair.
