"""Real MCP child-process handshake; isolated config prevents credential access."""

import asyncio
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def test_real_stdio_handshake_and_not_authenticated(tmp_path):
    async def check():
        bootstrap = (
            "import sys; from pathlib import Path; from icloud_agent import auth; "
            "auth.config_path = lambda: Path(sys.argv[1]); "
            "from icloud_agent.mcp_server import run; run()"
        )
        params = StdioServerParameters(
            command=sys.executable, args=["-c", bootstrap, str(tmp_path / "missing.json")]
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert len(tools.tools) == 13
                result = await session.call_tool("mail_folders", {"arguments": {}})
                payload = result.structuredContent or json.loads(result.content[0].text)
                assert not payload["ok"]
                assert payload["error"]["code"] == "not_authenticated"

    asyncio.run(check())
