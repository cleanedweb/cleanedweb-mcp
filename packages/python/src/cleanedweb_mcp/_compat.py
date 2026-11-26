"""The parts of the mcp SDK that changed between 1.x and 2.x, behind one interface.

mcp 2.x renamed McpError to MCPError (built from code and message), moved to the httpx2 HTTP
client, sends typed requests without the ClientRequest/ServerResult wrappers, and registers
server handlers as constructor arguments that receive (ctx, params). Python 3.10 resolves to
mcp 1.x, because httpx2 needs Python 3.11.
"""

from __future__ import annotations

from importlib.metadata import version as _version
from typing import Any

import mcp.types as types

MCP_MAJOR = int(_version("mcp").split(".")[0])

if MCP_MAJOR >= 2:
    import httpx2 as httpx
    from mcp.shared.exceptions import MCPError as McpError

    def mcp_error(code: int, message: str) -> McpError:
        return McpError(code, message)

    def client_request(request: Any) -> Any:
        return request

    def server_result(result: Any) -> Any:
        return result

else:
    import httpx
    from mcp.shared.exceptions import McpError

    def mcp_error(code: int, message: str) -> McpError:
        return McpError(types.ErrorData(code=code, message=message))

    def client_request(request: Any) -> Any:
        return types.ClientRequest(request)

    def server_result(result: Any) -> Any:
        return types.ServerResult(result)


__all__ = ["MCP_MAJOR", "McpError", "client_request", "httpx", "mcp_error", "server_result"]
