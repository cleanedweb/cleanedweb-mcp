# ChatGPT plugin package

Portable plugin package for the ChatGPT plugin directory (platform.openai.com → Plugins): `plugin.json`
(listing, review test cases, release notes under `extensions.com.openai`), `mcp.json` (the hosted MCP
server with OAuth dynamic client registration), the `cleanedweb` skill in provider-neutral wording, and
the logo. Build the upload with:

```sh
cd packages/chatgpt-plugin && zip -qrX ../../cleanedweb-chatgpt-plugin.zip plugin.json mcp.json skills assets
```

Bump `version` and `publication.release_notes` for every new upload. The demo video URL and the reviewer
sign-in details are entered in the portal's review details, not in the package.
