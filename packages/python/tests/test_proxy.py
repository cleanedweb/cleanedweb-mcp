import os
import sys
from contextlib import asynccontextmanager

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from cleanedweb_mcp import Config, create_server
from cleanedweb_mcp._compat import MCP_MAJOR, McpError

from .fake_upstream import TOOLS, FakeUpstream


@pytest.fixture
def upstream():
    fake = FakeUpstream()
    yield fake
    fake.close()


@asynccontextmanager
async def connect(url: str, api_key: str | None = None):
    server = create_server(Config(url=url, api_key=api_key), "9.9.9")
    if MCP_MAJOR >= 2:
        from mcp.client._memory import InMemoryTransport

        async with InMemoryTransport(server) as (read, write), ClientSession(read, write) as client:
            await client.initialize()
            yield client
    else:
        from mcp.shared.memory import create_connected_server_and_client_session

        async with create_connected_server_and_client_session(server) as client:
            yield client


def wire(model) -> dict:
    """A result as it goes over the wire (camelCase): mcp 2.x names the Python attributes in snake_case."""
    return model.model_dump(by_alias=True, exclude_none=True)


async def test_announces_itself_with_tools_capability_only(upstream):
    async with connect(upstream.url) as client:
        init = await client.initialize()
    info = wire(init)
    assert info["serverInfo"]["name"] == "cleanedweb"
    assert info["serverInfo"]["version"] == "9.9.9"
    assert "tools" in info["capabilities"]
    assert "prompts" not in info["capabilities"] and "resources" not in info["capabilities"]


async def test_no_network_until_first_request(upstream):
    async with connect(upstream.url):
        assert upstream.seen == []


async def test_tools_list_is_forwarded_unchanged(upstream):
    async with connect(upstream.url) as client:
        result = await client.list_tools()
    got = [t.model_dump(by_alias=True, exclude_none=True) for t in result.tools]
    assert got == TOOLS
    assert [s["method"] for s in upstream.seen] == ["initialize", "notifications/initialized", "tools/list"]
    assert upstream.seen[-1]["protocol_version"] == "2025-06-18"


async def test_tools_call_is_forwarded_with_structured_result(upstream):
    async with connect(upstream.url) as client:
        result = await client.call_tool("find_api", {"site": "www.blocket.se"})
    assert wire(result)["structuredContent"] == {"count": 1, "echo": {"site": "www.blocket.se"}}
    call = next(s for s in upstream.seen if s["method"] == "tools/call")
    assert call["params"]["name"] == "find_api"
    assert call["params"]["arguments"] == {"site": "www.blocket.se"}


async def test_api_key_is_sent_as_bearer(upstream):
    async with connect(upstream.url, "cw_secret") as client:
        await client.list_tools()
    assert all(s["authorization"] == "Bearer cw_secret" for s in upstream.seen)


async def test_no_authorization_header_without_key(upstream):
    async with connect(upstream.url) as client:
        await client.list_tools()
    assert all(s["authorization"] is None for s in upstream.seen)


async def test_upstream_jsonrpc_error_passes_through(upstream):
    async with connect(upstream.url) as client:
        with pytest.raises(McpError, match="Unknown tool: nope"):
            await client.call_tool("nope", {})


async def test_upstream_401_on_call_becomes_error_result_naming_the_key(upstream):
    async with connect(upstream.url) as client:
        await client.list_tools()
        upstream.fail_calls_with = 401
        result = await client.call_tool("run_api", {"api_id": "x"})
    assert wire(result).get("isError") is True
    assert "CLEANEDWEB_API_KEY" in wire(result)["content"][0]["text"]


async def test_upstream_401_on_handshake_names_the_key(upstream):
    upstream.fail_initialize_with = 401
    async with connect(upstream.url, "cw_bad") as client:
        with pytest.raises(McpError, match="CLEANEDWEB_API_KEY"):
            await client.list_tools()
        result = await client.call_tool("run_api", {"api_id": "x"})
    assert wire(result).get("isError") is True
    assert "CLEANEDWEB_API_KEY" in wire(result)["content"][0]["text"]


async def test_connection_recovers_after_an_upstream_error_status(upstream):
    async with connect(upstream.url) as client:
        await client.list_tools()
        upstream.fail_calls_with = 401
        assert wire(await client.call_tool("run_api", {"api_id": "x"})).get("isError") is True
        upstream.fail_calls_with = None
        result = await client.call_tool("find_api", {"site": "a"})
    assert wire(result).get("isError") is not True
    assert wire(result)["structuredContent"]["count"] == 1


async def test_unreachable_upstream_is_reported_per_request(upstream):
    async with connect("http://127.0.0.1:1/mcp") as client:
        with pytest.raises(McpError, match="Could not reach"):
            await client.list_tools()
        result = await client.call_tool("find_api", {})
    assert wire(result).get("isError") is True


async def test_binary_over_stdio(upstream, capfd):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "cleanedweb_mcp"],
        env={"PATH": os.environ.get("PATH", ""), "CLEANEDWEB_MCP_URL": upstream.url, "CLEANEDWEB_API_KEY": "cw_k"},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as client:
            await client.initialize()
            tools = await client.list_tools()
            assert [t.name for t in tools.tools] == ["find_api", "run_api"]
            result = await client.call_tool("find_api", {"site": "a"})
            assert wire(result)["structuredContent"]["count"] == 1
    assert upstream.seen[-1]["authorization"] == "Bearer cw_k"
