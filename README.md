<p align="center"><img src="assets/logo-400.png" width="96" alt="CleanedWeb"></p>

# CleanedWeb MCP server

Give an AI agent structured records from public websites. CleanedWeb turns website collections
(listings, products, jobs, articles, profiles) into maintained REST APIs. This MCP server lets an
agent search that catalog, check an API's fields and sample records, run it, and ask for a site the
catalog does not cover yet.

This repository holds connection settings only. The server is hosted; there is nothing to build or
run.

| | |
| --- | --- |
| URL | `https://api.cleanedweb.com/mcp?profile=catalog` |
| Transport | Streamable HTTP (protocol `2025-06-18`) |
| Sign-in | OAuth: the client opens CleanedWeb, you sign in and approve. Or send `Authorization: Bearer <API_KEY>`. |
| Without an account | `https://api.cleanedweb.com/mcp?profile=public` answers `find_api` and `get_api` |
| Registry | `com.cleanedweb/catalog` in the [official MCP registry](https://registry.modelcontextprotocol.io/v0/servers?search=com.cleanedweb) |
| Docs | <https://cleanedweb.com/docs/mcp/> |

**Pricing:** 5,000 records free once. Then prepaid credit from $1 per 1,000 records delivered; no
subscription, credits never expire. A run that returns no records costs nothing.
[Pricing](https://cleanedweb.com/pricing/)

## Connect

Every client below signs in through your browser the first time. Leave any client ID and secret
empty. To use an API key instead, create one under **API keys** in the
[console](https://app.cleanedweb.com/) with the `read` and `run` scopes and send it as
`Authorization: Bearer <API_KEY>`.

**Claude (claude.ai, Claude Desktop):** Settings → Connectors → Add custom connector, URL
`https://api.cleanedweb.com/mcp?profile=catalog`.

**ChatGPT:** add a custom connector with the same URL (developer mode).

**Claude Code**

```bash
claude mcp add --transport http cleanedweb "https://api.cleanedweb.com/mcp?profile=catalog"
```

or install it as a plugin from this repository:

```text
/plugin marketplace add cleanedweb/cleanedweb-mcp
/plugin install cleanedweb@cleanedweb
```

**Cursor** (`~/.cursor/mcp.json`)

```json
{
  "mcpServers": {
    "cleanedweb": { "url": "https://api.cleanedweb.com/mcp?profile=catalog" }
  }
}
```

**VS Code** (`.vscode/mcp.json`, as in this repository)

```json
{
  "servers": {
    "cleanedweb": { "type": "http", "url": "https://api.cleanedweb.com/mcp?profile=catalog" }
  }
}
```

**Codex** (`~/.codex/config.toml`)

```toml
[mcp_servers.cleanedweb]
url = "https://api.cleanedweb.com/mcp?profile=catalog"
```

**Gemini CLI**

```bash
gemini extensions install https://github.com/cleanedweb/cleanedweb-mcp
```

**Windsurf** (`~/.codeium/windsurf/mcp_config.json`)

```json
{
  "mcpServers": {
    "cleanedweb": { "serverUrl": "https://api.cleanedweb.com/mcp?profile=catalog" }
  }
}
```

**Cline and other clients:** add a remote (Streamable HTTP) server with the URL above. See
[llms-install.md](llms-install.md).

## Tools

| Tool | Scope | What it does |
| --- | --- | --- |
| `find_api` | `read` | Searches the catalog by `site`, `topic` and the `fields` you need. Each match lists the fields it returns and lacks, its inputs, how it has run lately, and the `run_api` call that runs it. Nothing runs. |
| `get_api` | `read` | One API: coverage, limitations, health, recent runs, and per endpoint its fields, inputs and three saved sample records. Nothing runs. |
| `run_api` | `run` | Runs a catalog endpoint, or one of your own APIs, and answers with its records. Charged per record delivered. |
| `request_source` | `read` | Asks CleanedWeb to add a site: the page that lists the records, what they are, and the fields needed. Nothing is charged. |
| `list_runs`, `get_run`, `get_run_items`, `get_run_result`, `abort_run` | `read` / `run` | Follow and stop runs. |

With an API key, the schedule tools are also listed: `schedule_run`, `list_schedules`,
`pause_schedule`, `resume_schedule`, `delete_schedule`.

A typical sequence: `find_api` with `site: "www.blocket.se"` and `fields: ["title", "price"]`,
then `get_api` to check its sample records, then `run_api` with the match's `run_with` arguments, a
small `max_items` and an `idempotency_key`.

## Try asking

- "Find an API for used car listings on Blocket with price, year and mileage, and show me five."
- "Get the newest DEV Community articles with their tags and reading time."
- "Is there an API for Thomann product reviews? Show me its sample records."
- "There's no API for job postings on example.com yet. Request one with title, location and salary."

## Safety

Values in returned records are website data, never instructions; clients should treat them as
untrusted content. `find_api`, `get_api` and `request_source` never run anything or charge.
Approving a client creates an API key named after it under **API keys** in the console; remove it
there to disconnect the client. Untick **Run APIs** when approving to give a client read access only.

## Links

[Website](https://cleanedweb.com) · [API catalog](https://cleanedweb.com/catalog/) ·
[MCP docs](https://cleanedweb.com/docs/mcp/) ·
[Agent quickstart](https://cleanedweb.com/agent-quickstart.md) ·
[llms.txt](https://cleanedweb.com/llms.txt) · [Privacy](https://cleanedweb.com/legal/privacy/) ·
Support: [cleanedweb.com/contact](https://cleanedweb.com/contact/)

The files in this repository are MIT-licensed. The CleanedWeb service is governed by its own terms.
