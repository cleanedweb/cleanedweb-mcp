import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport, StreamableHTTPError } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import {
  CallToolRequestSchema,
  CallToolResultSchema,
  ErrorCode,
  ListToolsRequestSchema,
  ListToolsResultSchema,
  McpError,
} from "@modelcontextprotocol/sdk/types.js";
import type { ProxyConfig } from "./config.js";

export interface Proxy {
  /** The stdio-facing server. Connect it to a transport. */
  server: Server;
  /** Close the upstream connection (the stdio side is closed by its transport). */
  close(): Promise<void>;
}

const NEEDS_KEY =
  "CleanedWeb needs an API key for this. Set CLEANEDWEB_API_KEY (create a key with the read and run " +
  "scopes under API keys at https://app.cleanedweb.com/) and restart the server.";

/** Unauthorized upstream answers carry the HTTP status in the error code or text. */
function isAuthError(err: unknown): boolean {
  if (err instanceof StreamableHTTPError) return err.code === 401 || err.code === 403;
  const msg = err instanceof Error ? err.message : String(err);
  return /\b(401|403)\b|unauthori[sz]ed/i.test(msg);
}

/**
 * A stdio MCP server that forwards `tools/list` and `tools/call` to the hosted CleanedWeb
 * server unchanged. It defines no tools of its own, so the list, schemas, annotations and
 * results are always the hosted server's.
 *
 * The upstream connection is made on the first request, so the stdio handshake never waits
 * on the network and a network failure is reported per request.
 */
export function createProxy(config: ProxyConfig, version: string): Proxy {
  const server = new Server(
    { name: "cleanedweb", version, title: "CleanedWeb", websiteUrl: "https://cleanedweb.com/docs/mcp/" },
    { capabilities: { tools: { listChanged: false } } },
  );

  let upstream: Promise<Client> | undefined;
  const connect = (): Promise<Client> => {
    if (!upstream) {
      const attempt = (async () => {
        const headers: Record<string, string> = {};
        if (config.apiKey) headers.Authorization = `Bearer ${config.apiKey}`;
        const transport = new StreamableHTTPClientTransport(new URL(config.url), { requestInit: { headers } });
        const client = new Client({ name: "cleanedweb-mcp", version });
        client.onclose = () => {
          if (upstream === attempt) upstream = undefined;
        };
        await client.connect(transport);
        return client;
      })();
      attempt.catch(() => {
        if (upstream === attempt) upstream = undefined;
      });
      upstream = attempt;
    }
    return upstream;
  };

  server.setRequestHandler(ListToolsRequestSchema, async (request) => {
    try {
      const client = await connect();
      // request() skips the client-side result checks callTool() adds, so the answer is the hosted one.
      return await client.request({ method: "tools/list", params: request.params }, ListToolsResultSchema);
    } catch (err) {
      if (err instanceof McpError) throw err;
      if (isAuthError(err)) throw new McpError(ErrorCode.InvalidRequest, NEEDS_KEY);
      throw new McpError(ErrorCode.InternalError, `Could not reach ${config.url}: ${(err as Error).message}`);
    }
  });

  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    try {
      const client = await connect();
      return await client.request({ method: "tools/call", params: request.params }, CallToolResultSchema);
    } catch (err) {
      // A tool-level problem the model can act on goes back as an error result, not a protocol error.
      if (err instanceof McpError) {
        if (/sign in|unauthori[sz]ed|api key/i.test(err.message)) {
          return { isError: true, content: [{ type: "text" as const, text: `${err.message}\n${NEEDS_KEY}` }] };
        }
        throw err;
      }
      const text = isAuthError(err)
        ? NEEDS_KEY
        : `Could not reach ${config.url}: ${(err as Error).message}`;
      return { isError: true, content: [{ type: "text" as const, text }] };
    }
  });

  return {
    server,
    async close() {
      const pending = upstream;
      upstream = undefined;
      if (pending) await (await pending.catch(() => undefined))?.close().catch(() => undefined);
    },
  };
}
