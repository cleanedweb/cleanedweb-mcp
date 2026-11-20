# CleanedWeb Claude Desktop extension (.mcpb)

Builds `dist/cleanedweb.mcpb`, an [MCP Bundle](https://github.com/modelcontextprotocol/mcpb)
(manifest version 0.3) that runs the [`@cleanedweb/mcp`](../npm) stdio proxy inside Claude Desktop.
The proxy is bundled into one file (`server/index.js`), so the extension needs no network install and
no `node_modules`; Claude Desktop supplies Node.

```bash
cd packages/mcpb
npm install
npm run build        # bundles, validates the manifest, packs ../../dist/cleanedweb.mcpb
```

Install it by opening the file in Claude Desktop (double-click it, or Settings → Extensions → Advanced settings →
Install Extension). The optional `api_key` setting is marked sensitive: Claude Desktop stores it securely
and passes it to the server as `CLEANEDWEB_API_KEY`. Left empty, the extension uses the
public profile (`find_api` and `get_api` only).

The version comes from `../npm/package.json`; the icon is `../../.claude-plugin/icon.png`. The bundle
is unsigned; sign it with `npx mcpb sign` and your own certificate before distributing it.
