"""Local stdio MCP server that forwards to CleanedWeb's hosted MCP server."""

from importlib.metadata import PackageNotFoundError, version

from .config import CATALOG_URL, PUBLIC_URL, Config, resolve_config
from .proxy import create_server

try:
    __version__ = version("cleanedweb-mcp")
except PackageNotFoundError:  # running from a source checkout
    __version__ = "0.0.0"

__all__ = ["CATALOG_URL", "PUBLIC_URL", "Config", "create_server", "resolve_config", "__version__"]
