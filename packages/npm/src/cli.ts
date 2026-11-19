#!/usr/bin/env node
import { readFileSync } from "node:fs";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { resolveConfig } from "./config.js";
import { createProxy } from "./proxy.js";

const pkg = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8")) as { version: string };
const arg = process.argv[2];

if (arg === "--version" || arg === "-v") {
  console.log(pkg.version);
} else if (arg === "--help" || arg === "-h") {
  console.log(
    `cleanedweb-mcp ${pkg.version}\n\n` +
      "Stdio MCP server that forwards to the hosted CleanedWeb server.\n\n" +
      "Environment:\n" +
      "  CLEANEDWEB_API_KEY   API key (read and run scopes). Without it only find_api and get_api work.\n" +
      "  CLEANEDWEB_MCP_URL   Use another endpoint than https://api.cleanedweb.com/mcp\n\n" +
      "Docs: https://cleanedweb.com/docs/mcp/",
  );
} else {
  const config = resolveConfig();
  if (config.hint) console.error(config.hint);
  const proxy = createProxy(config, pkg.version);
  await proxy.server.connect(new StdioServerTransport());
  const shutdown = () => void proxy.close().finally(() => process.exit(0));
  process.stdin.on("end", shutdown);
  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);
}
