"""Live check against the hosted public profile (free, read-only, no key):
initialize, tools/list and one find_api call, through the stdio proxy.

Run from packages/python:  python scripts/live_check.py
"""

import json
import os
import sys

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "cleanedweb_mcp"],
        env={"PATH": os.environ.get("PATH", "")},  # no CLEANEDWEB_API_KEY: public profile
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as client:
            # Read results in wire form (camelCase): mcp 2.x names the Python attributes in snake_case.
            init = (await client.initialize()).model_dump(by_alias=True, exclude_none=True)
            print("initialize:", init["serverInfo"]["name"], init["serverInfo"]["version"], init["capabilities"])
            tools = [t.name for t in (await client.list_tools()).tools]
            print("tools/list:", ", ".join(tools))
            assert "find_api" in tools and "get_api" in tools, "find_api/get_api missing from the public profile"
            result = await client.call_tool("find_api", {"site": "www.blocket.se", "fields": ["title", "price"], "limit": 2})
            found = result.model_dump(by_alias=True, exclude_none=True)
            data = found.get("structuredContent") or json.loads(found["content"][0]["text"])
            print("find_api isError:", bool(found.get("isError")), "count:", data.get("count"), "total:", data.get("total"))
            for m in data.get("matches", []):
                site = m.get("site")
                print("  match:", m.get("api_id"), m.get("endpoint_id", ""), "-", site.get("name") if isinstance(site, dict) else site)
            assert not found.get("isError"), "find_api returned an error"
    print("live check OK")


anyio.run(main)
