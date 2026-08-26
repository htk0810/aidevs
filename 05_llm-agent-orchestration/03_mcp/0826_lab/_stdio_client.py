"""개인화 건강 습관 코치 MCP Server 연결 도우미."""

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


SERVER_PATH = Path(__file__).with_name("mcp_server.py")


@asynccontextmanager
async def connect_to_health_coach_server():
    """stdio 자식 프로세스로 MCP Server를 실행하고 세션을 반환합니다."""
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_PATH)],
    )
    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield session
