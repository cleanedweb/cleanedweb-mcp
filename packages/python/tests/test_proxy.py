import os
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.exceptions import McpError
from mcp.shared.memory import create_connected_server_and_client_session

from cleanedweb_mcp import Config, create_server

from .fake_upstream import TOOLS, FakeUpstream


@pytest.fixture
def upstream():
    fake = FakeUpstream()
    yield fake
    fake.close()


def connect(url: str, api_key: str | None = None):
    return create_connected_server_and_client_session(create_server(Config(url=url, api_key=api_key), "9.9.9"))


async def test_announces_itself_with_tools_capability_only(upstream):
    async with connect(upstream.url) as client:
        init = await client.initialize()
    assert init.serverInfo.name == "cleanedweb"
    assert init.serverInfo.version == "9.9.9"
    assert init.capabilities.tools is not None
    assert init.capabilities.prompts is None and init.capabilities.resources is None


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
    assert result.structuredContent == {"count": 1, "echo": {"site": "www.blocket.se"}}
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
    assert result.isError is True
    assert "CLEANEDWEB_API_KEY" in result.content[0].text


async def test_connection_recovers_after_an_upstream_error_status(upstream):
    async with connect(upstream.url) as client:
        await client.list_tools()
        upstream.fail_calls_with = 401
        assert (await client.call_tool("run_api", {"api_id": "x"})).isError is True
        upstream.fail_calls_with = None
        result = await client.call_tool("find_api", {"site": "a"})
    assert result.isError is not True
    assert result.structuredContent["count"] == 1


async def test_unreachable_upstream_is_reported_per_request(upstream):
    async with connect("http://127.0.0.1:1/mcp") as client:
        with pytest.raises(McpError, match="Could not reach"):
            await client.list_tools()
        result = await client.call_tool("find_api", {})
    assert result.isError is True


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
            assert result.structuredContent["count"] == 1
    assert upstream.seen[-1]["authorization"] == "Bearer cw_k"
