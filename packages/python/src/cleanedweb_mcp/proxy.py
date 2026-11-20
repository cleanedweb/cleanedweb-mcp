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
import httpx
import mcp.types as types
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.server.lowlevel import Server
from mcp.shared.exceptions import McpError

from .config import Config

log = logging.getLogger("cleanedweb_mcp")

NEEDS_KEY = (
    "CleanedWeb needs an API key for this. Set CLEANEDWEB_API_KEY (create a key with the read and run "
    "scopes under API keys at https://app.cleanedweb.com/) and restart the server."
)


def _is_auth_error(err: BaseException) -> bool:
    for e in _leaves(err):
        if isinstance(e, httpx.HTTPStatusError) and e.response.status_code in (401, 403):
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

    async def request(self, request: types.ClientRequest, result_type: type):
        """Send one request upstream. Raises McpError for an upstream JSON-RPC error, any other
        exception when the connection fails (the transport dies on an HTTP error status, and
        pending requests would otherwise wait forever)."""
        conn = await self._connection()
        session = conn.session
        assert session is not None
        outcome: list = []

        async def send(scope: anyio.CancelScope) -> None:
            try:
                outcome.append((True, await session.send_request(request, result_type)))
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
        try:
            async with httpx.AsyncClient(
                headers=headers, timeout=httpx.Timeout(30.0, read=300.0), follow_redirects=False
            ) as http:
                async with streamable_http_client(self._config.url, http_client=http) as (read, write, _):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        conn.session = session
                        conn.ready.set()
                        await conn.stop.wait()
        except BaseException as err:  # noqa: BLE001 - reported to whoever is waiting
            conn.error = err
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

    server: Server = Server(
        "cleanedweb",
        version=version,
        website_url="https://cleanedweb.com/docs/mcp/",
        lifespan=lifespan,
    )

    def upstream() -> Upstream:
        return server.request_context.lifespan_context

    async def list_tools(req: types.ListToolsRequest) -> types.ServerResult:
        up = upstream()
        try:
            result = await up.request(
                types.ClientRequest(types.ListToolsRequest(params=req.params)), types.ListToolsResult
            )
            return types.ServerResult(result)
        except McpError:
            raise
        except BaseException as err:  # noqa: BLE001
            up.reset()
            if _is_auth_error(err):
                raise McpError(types.ErrorData(code=types.INVALID_REQUEST, message=NEEDS_KEY)) from err
            raise McpError(
                types.ErrorData(code=types.INTERNAL_ERROR, message=f"Could not reach {config.url}: {_describe(err)}")
            ) from err

    async def call_tool(req: types.CallToolRequest) -> types.ServerResult:
        up = upstream()
        try:
            # send_request skips the client-side result checks call_tool() adds, so the answer is the hosted one.
            result = await up.request(
                types.ClientRequest(types.CallToolRequest(params=req.params)), types.CallToolResult
            )
            return types.ServerResult(result)
        except McpError as err:
            lowered = err.error.message.lower()
            if "sign in" in lowered or "unauthorized" in lowered or "api key" in lowered:
                return _error_result(f"{err.error.message}\n{NEEDS_KEY}")
            raise
        except BaseException as err:  # noqa: BLE001
            up.reset()
            text = NEEDS_KEY if _is_auth_error(err) else f"Could not reach {config.url}: {_describe(err)}"
            return _error_result(text)

    server.request_handlers[types.ListToolsRequest] = list_tools
    server.request_handlers[types.CallToolRequest] = call_tool
    return server


def _error_result(text: str) -> types.ServerResult:
    return types.ServerResult(types.CallToolResult(isError=True, content=[types.TextContent(type="text", text=text)]))
