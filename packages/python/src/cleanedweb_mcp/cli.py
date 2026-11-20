from __future__ import annotations

import sys

import anyio
from mcp.server.stdio import stdio_server

from . import __version__
from .config import resolve_config
from .proxy import create_server

HELP = f"""cleanedweb-mcp {__version__}

Stdio MCP server that forwards to the hosted CleanedWeb server.

Environment:
  CLEANEDWEB_API_KEY   API key (read and run scopes). Without it only find_api and get_api work.
  CLEANEDWEB_MCP_URL   Use another endpoint than https://api.cleanedweb.com/mcp

Docs: https://cleanedweb.com/docs/mcp/"""


async def serve() -> None:
    config = resolve_config()
    if config.hint:
        print(config.hint, file=sys.stderr, flush=True)
    server = create_server(config, __version__)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    if arg in ("--version", "-v"):
        print(__version__)
    elif arg in ("--help", "-h"):
        print(HELP)
    else:
        try:
            anyio.run(serve)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
