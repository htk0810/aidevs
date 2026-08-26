"""OpenAI API 없이 MCP Server와 세 Tool의 기본 동작을 확인합니다."""

import asyncio

from _stdio_client import connect_to_health_coach_server


async def main() -> None:
    async with connect_to_health_coach_server() as session:
        discovered = {tool.name for tool in (await session.list_tools()).tools}
        expected = {"get_health_summary", "get_daily_context", "save_daily_plan"}
        assert discovered == expected, discovered

        summary = await session.call_tool(
            "get_health_summary", {"user_id": "demo-user", "days": 7}
        )
        assert not summary.isError

        context = await session.call_tool(
            "get_daily_context",
            {"user_id": "demo-user", "date": "2026-08-26"},
        )
        assert not context.isError

        unapproved = await session.call_tool(
            "save_daily_plan",
            {
                "user_id": "demo-user",
                "date": "2026-08-26",
                "action_type": "exercise",
                "action": "실내 스트레칭",
                "scheduled_time": "19:30",
                "duration_minutes": 15,
                "user_confirmed": False,
            },
        )
        assert unapproved.isError

        approved = await session.call_tool(
            "save_daily_plan",
            {
                "user_id": "demo-user",
                "date": "2026-08-26",
                "action_type": "exercise",
                "action": "실내 스트레칭",
                "scheduled_time": "19:30",
                "duration_minutes": 15,
                "user_confirmed": True,
            },
        )
        assert not approved.isError

    print("MCP smoke test passed: 3 tools, approval guard, save flow")


if __name__ == "__main__":
    asyncio.run(main())
