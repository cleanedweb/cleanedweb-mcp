// Live check against the hosted public profile (free, read-only, no key):
// initialize, tools/list and one find_api call, through the stdio proxy.
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { fileURLToPath } from "node:url";

const cli = fileURLToPath(new URL("../dist/cli.js", import.meta.url));
const transport = new StdioClientTransport({
  command: process.execPath,
  args: [cli],
  env: { PATH: process.env.PATH ?? "" }, // no CLEANEDWEB_API_KEY: public profile
  stderr: "inherit",
});
const client = new Client({ name: "live-check", version: "0" });
await client.connect(transport);
console.log("initialize:", JSON.stringify(client.getServerVersion()), JSON.stringify(client.getServerCapabilities()));

const { tools } = await client.listTools();
console.log("tools/list:", tools.map((t) => t.name).join(", "));
if (!tools.some((t) => t.name === "find_api") || !tools.some((t) => t.name === "get_api")) {
  throw new Error("find_api/get_api missing from the public profile");
}

const found = await client.callTool({ name: "find_api", arguments: { site: "www.blocket.se", fields: ["title", "price"], limit: 2 } });
const data = found.structuredContent ?? JSON.parse(found.content[0].text);
console.log("find_api isError:", Boolean(found.isError), "count:", data.count, "total:", data.total);
for (const m of data.matches ?? []) console.log("  match:", m.api_id, m.endpoint_id ?? "", "-", m.site?.name ?? m.site ?? "");
if (found.isError) throw new Error("find_api returned an error");

await client.close();
console.log("live check OK");
