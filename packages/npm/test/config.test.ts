import { describe, expect, it } from "vitest";
import { CATALOG_URL, PUBLIC_URL, resolveConfig } from "../src/config.js";

describe("resolveConfig", () => {
  it("uses the public profile and hints on stderr without a key", () => {
    const c = resolveConfig({});
    expect(c.url).toBe(PUBLIC_URL);
    expect(c.apiKey).toBeUndefined();
    expect(c.hint).toMatch(/CLEANEDWEB_API_KEY/);
  });

  it("uses the catalog profile with a key and prints no hint", () => {
    const c = resolveConfig({ CLEANEDWEB_API_KEY: " cw_key " });
    expect(c.url).toBe(CATALOG_URL);
    expect(c.apiKey).toBe("cw_key");
    expect(c.hint).toBeUndefined();
  });

  it("treats empty and unresolved placeholder values as unset", () => {
    expect(resolveConfig({ CLEANEDWEB_API_KEY: "" }).apiKey).toBeUndefined();
    expect(resolveConfig({ CLEANEDWEB_API_KEY: "${user_config.api_key}" }).url).toBe(PUBLIC_URL);
    expect(resolveConfig({ CLEANEDWEB_MCP_URL: "  " }).url).toBe(PUBLIC_URL);
  });

  it("lets CLEANEDWEB_MCP_URL override the endpoint", () => {
    const c = resolveConfig({ CLEANEDWEB_API_KEY: "k", CLEANEDWEB_MCP_URL: "http://localhost:9/mcp" });
    expect(c.url).toBe("http://localhost:9/mcp");
  });
});
