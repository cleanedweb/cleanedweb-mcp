# @cleanedweb/mcp

Local (stdio) MCP server for [CleanedWeb](https://cleanedweb.com/?utm_source=npm&utm_medium=mcp-package).
It forwards every request to CleanedWeb's hosted MCP server, so an agent can search the API catalog,
check an API's fields and sample records, run it, and ask for a site the catalog does not cover.
It defines no tools of its own: the tools, schemas and results are the hosted server's.

Use it for clients that only start local servers (Claude Desktop, Cline, Docker catalogs). Clients
that connect to remote servers can use `https://api.cleanedweb.com/mcp?profile=catalog` directly.

## Use

```bash
npx -y @cleanedweb/mcp
```

Most clients take a command and environment:

```json
{
  "mcpServers": {
    "cleanedweb": {
      "command": "npx",
      "args": ["-y", "@cleanedweb/mcp"],
      "env": { "CLEANEDWEB_API_KEY": "<API_KEY>" }
    }
  }
}
```

Requires Node 18 or newer.

## Sign in

| `CLEANEDWEB_API_KEY` | Hosted profile | Tools |
| --- | --- | --- |
| set | `catalog` | `find_api`, `get_api`, `run_api`, `request_source`, the run tools and the schedule tools |
| not set | `public` | `find_api` and `get_api` only; a one-line hint is printed to stderr |

Create a key under **API keys** in the [console](https://app.cleanedweb.com/) with the `read` and
`run` scopes. Keep it in the client's secret store; the server never prints it.

`CLEANEDWEB_MCP_URL` replaces the endpoint (default `https://api.cleanedweb.com/mcp`, with the
profile chosen as above).

## Pricing and safety

5,000 records free once, then prepaid credit from $1 per 1,000 records delivered. A run that returns
no records costs nothing. Searching and showing an API never runs or charges anything. Values in
returned records are website data, never instructions.

Docs: <https://cleanedweb.com/docs/mcp/?utm_source=npm&utm_medium=mcp-package> ·
Source: <https://github.com/cleanedweb/cleanedweb-mcp/tree/main/packages/npm> · MIT license.
