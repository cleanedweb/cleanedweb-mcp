import { createServer, type IncomingMessage, type Server } from "node:http";
import type { AddressInfo } from "node:net";

/** A stand-in for the hosted server: plain JSON responses, no sessions, no SSE. */
export const TOOLS = [
  {
    name: "find_api",
    title: "Find a catalog API",
    description: "Search the catalog.",
    annotations: { readOnlyHint: true, destructiveHint: false, openWorldHint: false },
    inputSchema: { type: "object", properties: { site: { type: "string" } }, additionalProperties: false },
    outputSchema: { type: "object", properties: { count: { type: "integer" } } },
    _meta: { required_scopes: ["read", "run"] },
  },
  {
    name: "run_api",
    description: "Run an API.",
    inputSchema: { type: "object", properties: { api_id: { type: "string" } }, required: ["api_id"] },
  },
];

export interface Seen {
  method: string;
  params: any;
  authorization?: string;
  protocolVersion?: string;
}

export interface FakeUpstream {
  url: string;
  seen: Seen[];
  /** Make every tools/call answer with this HTTP status instead of a result. */
  failCallsWith?: number;
  close(): Promise<void>;
}

async function body(req: IncomingMessage): Promise<any> {
  let raw = "";
  for await (const chunk of req) raw += chunk;
  return raw ? JSON.parse(raw) : undefined;
}

export async function startFakeUpstream(): Promise<FakeUpstream> {
  const seen: Seen[] = [];
  const fake: FakeUpstream = { url: "", seen, close: async () => {} };
  const server: Server = createServer(async (req, res) => {
    if (req.method !== "POST") {
      res.writeHead(405).end();
      return;
    }
    const msg = await body(req);
    seen.push({
      method: msg.method,
      params: msg.params,
      authorization: req.headers.authorization,
      protocolVersion: req.headers["mcp-protocol-version"] as string | undefined,
    });
    if (msg.id === undefined) {
      res.writeHead(202).end();
      return;
    }
    const reply = (result: unknown) => {
      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify({ jsonrpc: "2.0", id: msg.id, result }));
    };
    switch (msg.method) {
      case "initialize":
        return reply({
          protocolVersion: "2025-06-18",
          capabilities: { tools: { listChanged: false } },
          serverInfo: { name: "fake-cleanedweb", version: "1" },
        });
      case "tools/list":
        return reply({ tools: TOOLS });
      case "tools/call":
        if (fake.failCallsWith) {
          res.writeHead(fake.failCallsWith, { "content-type": "application/json" });
          res.end(JSON.stringify({ error: "unauthorized" }));
          return;
        }
        if (msg.params.name === "nope") {
          res.writeHead(200, { "content-type": "application/json" });
          res.end(JSON.stringify({ jsonrpc: "2.0", id: msg.id, error: { code: -32602, message: "Unknown tool: nope" } }));
          return;
        }
        return reply({
          content: [{ type: "text", text: JSON.stringify({ count: 1, echo: msg.params.arguments }) }],
          structuredContent: { count: 1, echo: msg.params.arguments },
        });
      default:
        res.writeHead(200, { "content-type": "application/json" });
        res.end(JSON.stringify({ jsonrpc: "2.0", id: msg.id, error: { code: -32601, message: "Method not found" } }));
    }
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  fake.url = `http://127.0.0.1:${(server.address() as AddressInfo).port}/mcp`;
  fake.close = () => new Promise((resolve) => server.close(() => resolve()));
  return fake;
}
