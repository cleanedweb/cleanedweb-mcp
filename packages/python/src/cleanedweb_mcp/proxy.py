"""A stdio MCP server that forwards tools/list and tools/call to the hosted server unchanged.

It defines no tools of its own, so the list, schemas, annotations and results are always the
hosted server's. The upstream connection is made on the first request, so the stdio handshake
never waits on the network and a network failure is reported per request.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import anyio
import mcp.types as types
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.server.lowlevel import Server

from ._compat import MCP_MAJOR, McpError, client_request, httpx, mcp_error, server_result
from .config import Config

log = logging.getLogger("cleanedweb_mcp")

NEEDS_KEY = (
    "CleanedWeb needs an API key for this. Set CLEANEDWEB_API_KEY (create a key with the read and run "
    "scopes under API keys at https://app.cleanedweb.com/) and restart the server."
)


def _is_auth_error(err: BaseException) -> bool:
    for e in _leaves(err):
        if isinstance(e, UpstreamAuthError) or (
            isinstance(e, httpx.HTTPStatusError) and e.response.status_code in (401, 403)
        ):
            return True
        if "401" in str(e) or "403" in str(e) or "unauthorized" in str(e).lower():
            return True
    return False


def _leaves(err: BaseException) -> list[BaseException]:
    # Duck-typed so it also covers the exceptiongroup backport on Python 3.10.
    subs = getattr(err, "exceptions", None)
    if isinstance(subs, (list, tuple)) and subs:
        return [leaf for sub in subs for leaf in _leaves(sub)]
    return [err]


def _describe(err: BaseException) -> str:
    return "; ".join(f"{type(e).__name__}: {e}" if str(e) else type(e).__name__ for e in _leaves(err))


class _Connection:
    """One upstream session, and what happened to it."""

    def __init__(self) -> None:
        self.session: ClientSession | None = None
        self.ready = anyio.Event()
        self.dead = anyio.Event()
        self.stop = anyio.Event()
        self.error: BaseException | None = None
        # Last 401/403 the hosted server answered. mcp 2.x turns an HTTP error status into a generic
        # JSON-RPC error and keeps the connection, so the status is only visible here.
        self.auth_status: int | None = None


class UpstreamAuthError(ConnectionError):
    def __init__(self, status: int) -> None:
        super().__init__(f"the hosted server answered HTTP {status}")


class Upstream:
    """A lazily opened session to the hosted server, kept alive by a background task."""

    def __init__(self, config: Config, task_group: anyio.abc.TaskGroup) -> None:
        self._config = config
        self._tg = task_group
        self._lock = anyio.Lock()
        self._conn: _Connection | None = None
        self._closing = False

    async def _connection(self) -> _Connection:
        async with self._lock:
            conn = self._conn
            if conn is None or conn.dead.is_set():
                conn = self._conn = _Connection()
                self._tg.start_soon(self._run, conn)
                await conn.ready.wait()
            if conn.session is None:
                assert conn.error is not None
                raise conn.error
            return conn

    async def request(self, request, result_type: type):
        """Send one request upstream. Raises McpError (MCPError on mcp 2.x) for an upstream JSON-RPC error, any other
        exception when the connection fails (the transport dies on an HTTP error status, and
        pending requests would otherwise wait forever)."""
        conn = await self._connection()
        session = conn.session
        assert session is not None
        outcome: list = []
        conn.auth_status = None

        async def send(scope: anyio.CancelScope) -> None:
            try:
                outcome.append((True, await session.send_request(client_request(request), result_type)))
            except Exception as err:  # noqa: BLE001 - re-raised below
                outcome.append((False, err))
            scope.cancel()

        async def watch(scope: anyio.CancelScope) -> None:
            await conn.dead.wait()
            scope.cancel()

        async with anyio.create_task_group() as tg:
            tg.start_soon(send, tg.cancel_scope)
            tg.start_soon(watch, tg.cancel_scope)
        if outcome:
            ok, value = outcome[0]
            if ok:
                return value
            if conn.auth_status is not None:
                raise UpstreamAuthError(conn.auth_status) from value
            raise value
        raise conn.error or ConnectionError("connection to the hosted server closed")

    def reset(self) -> None:
        """Drop the connection; the next request opens a new one."""
        if self._conn is not None:
            self._conn.stop.set()

    async def aclose(self) -> None:
        self._closing = True
        self.reset()

    async def _run(self, conn: _Connection) -> None:
        headers = {"Authorization": f"Bearer {self._config.api_key}"} if self._config.api_key else None

        async def note_auth_status(response) -> None:
            if response.status_code in (401, 403):
                conn.auth_status = response.status_code

        try:
            async with httpx.AsyncClient(
                headers=headers,
                timeout=httpx.Timeout(30.0, read=300.0),
                follow_redirects=False,
                event_hooks={"response": [note_auth_status]},
            ) as http:
                # mcp 1.x yields (read, write, get_session_id); 2.x yields (read, write).
                async with streamable_http_client(self._config.url, http_client=http) as streams:
                    async with ClientSession(streams[0], streams[1]) as session:
                        await session.initialize()
                        conn.session = session
                        conn.ready.set()
                        await conn.stop.wait()
        except BaseException as err:  # noqa: BLE001 - reported to whoever is waiting
            conn.error = err
            if conn.session is None and conn.auth_status is not None:
                # The handshake itself was refused (a bad key): say so rather than "could not reach".
                auth_error = UpstreamAuthError(conn.auth_status)
                auth_error.__cause__ = err
                conn.error = auth_error
            if conn.session is not None and not self._closing and not conn.stop.is_set():
                log.debug("upstream closed: %s", err)
            if isinstance(err, (KeyboardInterrupt, SystemExit)):
                raise
        finally:
            if conn.error is None and not conn.ready.is_set():
                conn.error = ConnectionError("connection to the hosted server closed")
            conn.dead.set()
            conn.ready.set()


def create_server(config: Config, version: str) -> Server:
    @asynccontextmanager
    async def lifespan(_: Server) -> AsyncIterator[Upstream]:
        async with anyio.create_task_group() as tg:
            upstream = Upstream(config, tg)
            try:
                yield upstream
            finally:
                await upstream.aclose()

    async def list_tools(up: Upstream, params) -> types.ListToolsResult:
        try:
            return await up.request(types.ListToolsRequest(params=params), types.ListToolsResult)
        except McpError:
            raise
        except BaseException as err:  # noqa: BLE001
            up.reset()
            if _is_auth_error(err):
                raise mcp_error(types.INVALID_REQUEST, NEEDS_KEY) from err
            raise mcp_error(types.INTERNAL_ERROR, f"Could not reach {config.url}: {_describe(err)}") from err

    async def call_tool(up: Upstream, params) -> types.CallToolResult:
        try:
            # send_request skips the client-side result checks call_tool() adds, so the answer is the hosted one.
            return await up.request(types.CallToolRequest(params=params), types.CallToolResult)
        except McpError as err:
            lowered = err.error.message.lower()
            if "sign in" in lowered or "unauthorized" in lowered or "api key" in lowered:
                return _error_result(f"{err.error.message}\n{NEEDS_KEY}")
            raise
        except BaseException as err:  # noqa: BLE001
            up.reset()
            text = NEEDS_KEY if _is_auth_error(err) else f"Could not reach {config.url}: {_describe(err)}"
            return _error_result(text)

    meta = {"version": version, "website_url": "https://cleanedweb.com/docs/mcp/", "lifespan": lifespan}

    if MCP_MAJOR >= 2:
        # Handlers are constructor arguments and get (ctx, params); results go back unwrapped.
        async def on_list_tools(ctx, params) -> types.ListToolsResult:
            return await list_tools(ctx.lifespan_context, params)

        async def on_call_tool(ctx, params) -> types.CallToolResult:
            return await call_tool(ctx.lifespan_context, params)

        return Server("cleanedweb", **meta, on_list_tools=on_list_tools, on_call_tool=on_call_tool)

    server: Server = Server("cleanedweb", **meta)

    async def handle_list_tools(req: types.ListToolsRequest) -> types.ServerResult:
        return server_result(await list_tools(server.request_context.lifespan_context, req.params))

    async def handle_call_tool(req: types.CallToolRequest) -> types.ServerResult:
        return server_result(await call_tool(server.request_context.lifespan_context, req.params))

    server.request_handlers[types.ListToolsRequest] = handle_list_tools
    server.request_handlers[types.CallToolRequest] = handle_call_tool
    return server


def _error_result(text: str) -> types.CallToolResult:
    return types.CallToolResult(isError=True, content=[types.TextContent(type="text", text=text)])
