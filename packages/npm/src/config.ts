/** Where the proxy connects and how it signs in, decided from the environment. */

export const CATALOG_URL = "https://api.cleanedweb.com/mcp?profile=catalog";
export const PUBLIC_URL = "https://api.cleanedweb.com/mcp?profile=public";

export interface ProxyConfig {
  /** Hosted MCP endpoint the proxy forwards to. */
  url: string;
  /** API key sent as `Authorization: Bearer`, if any. */
  apiKey?: string;
  /** One-line stderr hint to print at start-up, if any. */
  hint?: string;
}

/**
 * An env value counts as set only when it holds text. Empty strings and an unresolved
 * `${user_config.x}` placeholder (what a Claude Desktop bundle passes when the user left
 * the field blank) mean "not set".
 */
function clean(value: string | undefined): string | undefined {
  const v = value?.trim();
  if (!v || /^\$\{[^}]*\}$/.test(v)) return undefined;
  return v;
}

export function resolveConfig(env: NodeJS.ProcessEnv = process.env): ProxyConfig {
  const apiKey = clean(env.CLEANEDWEB_API_KEY);
  const override = clean(env.CLEANEDWEB_MCP_URL);
  const url = override ?? (apiKey ? CATALOG_URL : PUBLIC_URL);
  let hint: string | undefined;
  if (!apiKey) {
    hint =
      "cleanedweb-mcp: no CLEANEDWEB_API_KEY set; only find_api and get_api work. " +
      "Create a key with the read and run scopes at https://app.cleanedweb.com/ to run APIs.";
  }
  return { url, apiKey, hint };
}
