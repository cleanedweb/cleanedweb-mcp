import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { fileURLToPath } from "node:url";
import { createProxy, type Proxy } from "../src/index.js";
import { startFakeUpstream, TOOLS, type FakeUpstream } from "./fake-upstream.js";

let upstream: FakeUpstream;
let proxy: Proxy | undefined;
let client: Client | undefined;

beforeEach(async () => {
  upstream = await startFakeUpstream();
});
afterEach(async () => {
  await client?.close();
  await proxy?.close();
  await upstream.close();
  client = proxy = undefined;
});

async function connectInMemory(config: { apiKey?: string; url?: string }) {
  proxy = createProxy({ url: config.url ?? upstream.url, apiKey: config.apiKey }, "9.9.9");
  const [a, b] = InMemoryTransport.createLinkedPair();
  await proxy.server.connect(a);
  client = new Client({ name: "test", version: "0" });
  await client.connect(b);
  return client;
}

describe("proxy (in memory)", () => {
  it("announces itself as cleanedweb with a tools capability only", async () => {
    const c = await connectInMemory({});
    expect(c.getServerVersion()).toMatchObject({ name: "cleanedweb", version: "9.9.9" });
    expect(c.getServerCapabilities()).toEqual({ tools: { listChanged: false } });
  });

  it("does not touch the network until the first request", async () => {
    await connectInMemory({});
    expect(upstream.seen).toEqual([]);
  });

  it("forwards tools/list unchanged, including annotations and _meta", async () => {
    const c = await connectInMemory({});
    const { tools } = await c.listTools();
    expect(tools).toEqual(TOOLS);
    const methods = upstream.seen.map((s) => s.method);
    expect(methods).toEqual(["initialize", "notifications/initialized", "tools/list"]);
    expect(upstream.seen.at(-1)?.protocolVersion).toBe("2025-06-18");
  });

  it("forwards tools/call arguments and returns the structured result", async () => {
    const c = await connectInMemory({});
    const result = await c.callTool({ name: "find_api", arguments: { site: "www.blocket.se" } });
    expect(result.structuredContent).toEqual({ count: 1, echo: { site: "www.blocket.se" } });
    expect(upstream.seen.at(-1)).toMatchObject({ method: "tools/call", params: { name: "find_api", arguments: { site: "www.blocket.se" } } });
  });

  it("sends the API key as a Bearer header", async () => {
    const c = await connectInMemory({ apiKey: "cw_secret" });
    await c.listTools();
    expect(upstream.seen.every((s) => s.authorization === "Bearer cw_secret")).toBe(true);
  });

  it("sends no Authorization header without a key", async () => {
    const c = await connectInMemory({});
    await c.listTools();
    expect(upstream.seen.every((s) => s.authorization === undefined)).toBe(true);
  });

  it("passes an upstream JSON-RPC error through", async () => {
    const c = await connectInMemory({});
    await expect(c.callTool({ name: "nope", arguments: {} })).rejects.toThrow(/Unknown tool: nope/);
  });

  it("turns an upstream 401 on a call into an error result that names the key", async () => {
    const c = await connectInMemory({});
    await c.listTools();
    upstream.failCallsWith = 401;
    const result = await c.callTool({ name: "run_api", arguments: { api_id: "x" } });
    expect(result.isError).toBe(true);
    expect(JSON.stringify(result.content)).toMatch(/CLEANEDWEB_API_KEY/);
  });

  it("reports an unreachable upstream per request and recovers when it returns", async () => {
    const c = await connectInMemory({ url: "http://127.0.0.1:1/mcp" });
    await expect(c.listTools()).rejects.toThrow(/Could not reach/);
    const result = await c.callTool({ name: "find_api", arguments: {} });
    expect(result.isError).toBe(true);
  });
});

describe("cleanedweb-mcp binary (stdio)", () => {
  const cli = fileURLToPath(new URL("../dist/cli.js", import.meta.url));

  async function spawn(env: Record<string, string>) {
    const transport = new StdioClientTransport({
      command: process.execPath,
      args: [cli],
      env: { PATH: process.env.PATH ?? "", ...env },
      stderr: "pipe",
    });
    const stderr: string[] = [];
    transport.stderr?.on("data", (d) => stderr.push(String(d)));
    client = new Client({ name: "test", version: "0" });
    await client.connect(transport);
    return { stderr };
  }

  it("lists and calls through the fake upstream; hints on stderr without a key", async () => {
    const { stderr } = await spawn({ CLEANEDWEB_MCP_URL: upstream.url });
    const { tools } = await client!.listTools();
    expect(tools.map((t) => t.name)).toEqual(["find_api", "run_api"]);
    const result = await client!.callTool({ name: "find_api", arguments: { site: "a" } });
    expect(result.structuredContent).toMatchObject({ count: 1 });
    expect(stderr.join("")).toMatch(/no CLEANEDWEB_API_KEY set/);
  });

  it("prints no hint and sends the key when CLEANEDWEB_API_KEY is set", async () => {
    const { stderr } = await spawn({ CLEANEDWEB_MCP_URL: upstream.url, CLEANEDWEB_API_KEY: "cw_k" });
    await client!.listTools();
    expect(stderr.join("")).toBe("");
    expect(upstream.seen.at(-1)?.authorization).toBe("Bearer cw_k");
  });
});
