# Fathom MCP server

`fathom mcp` runs a stdio [MCP](https://modelcontextprotocol.io) server (`mcp.server.fastmcp.FastMCP`)
exposing four tools over the four frozen output contracts (`03-lld.md` §3, §4):

| Tool | Arguments | Returns |
|------|-----------|---------|
| `get_quote` | `ticker` | JSON of `QuoteCard` |
| `list_filings` | `ticker` | JSON array of `Filing` |
| `get_briefing` | `ticker` | JSON of `Briefing` |
| `ask_filings` | `ticker`, `question` | JSON of `Answer` |

Every tool description ends with the configured disclaimer. Tools never raise: a known failure
(e.g. an unknown ticker) comes back as the JSON text `{"ok": false, "error": {"code", "message"}}`
instead of an MCP protocol error, so a host can render it directly.

The server reads `Settings.from_env()` at call time, so the same environment variables that
configure the CLI and HTTP API (`FATHOM_LLM_PROVIDER`, `FATHOM_DATA_DIR`, `PORTKEY_API_KEY`,
`ANTHROPIC_API_KEY`, etc.) apply to MCP calls too.

## Registering with Claude Desktop / Claude Code

Add an entry to the host's MCP server configuration (Claude Desktop's
`claude_desktop_config.json`, or a project's `.mcp.json` for Claude Code):

```json
{
  "mcpServers": {
    "fathom": {
      "command": "uv",
      "args": ["run", "fathom", "mcp"],
      "cwd": "/absolute/path/to/fathom"
    }
  }
}
```

`cwd` must be the repository root (so `data/`, `audit/`, and the installed `fathom` package
resolve correctly). Set any needed environment variables (`FATHOM_LLM_PROVIDER`,
`PORTKEY_API_KEY`, `ANTHROPIC_API_KEY`, `FATHOM_DATA_DIR`, `FATHOM_AUDIT_PATH`, ...) either in the
host's `env` block for this server entry, or in the shell `uv run` inherits from.

The `mcp` extra must be installed for this command to work: `uv sync --extra mcp` (or however the
project's `mcp` dependency group is installed). Without it, `fathom mcp` exits 2 with
`error NOT_AVAILABLE: mcp arrives in T-012`.
