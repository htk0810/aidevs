"""MCP Tool을 사용하는 개인화 건강 습관 코치 AI Agent.

읽기 전용 Tool로 계획을 먼저 제안하고, 사용자가 명시적으로 동의한 경우에만
쓰기 Tool을 공개해 계획을 저장합니다. 의료 진단이나 처방은 수행하지 않습니다.

실행:
    python ai_agent.py
"""

import asyncio
import json
import os
from datetime import date
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import AsyncOpenAI

from _stdio_client import connect_to_health_coach_server


ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
MAX_TOOL_ROUNDS = 4
READ_TOOLS = {"get_health_summary", "get_daily_context"}
WRITE_TOOLS = {"save_daily_plan"}

COACH_INSTRUCTIONS = """
당신은 개인화 건강 습관 코치 AI Agent입니다.

목표:
- 사용자의 최근 식단·운동·수면 습관과 오늘 상황을 확인합니다.
- 오늘 실행할 수 있는 작고 구체적인 행동 한 가지를 제안합니다.
- 계획의 시간, 소요 시간, 선택 이유를 한국어로 간결하게 설명합니다.

필수 규칙:
- 계획을 제안하기 전에 get_health_summary와 get_daily_context를 모두 호출하세요.
- user_id는 demo-user를 사용하세요.
- 날짜는 사용자 요청에 포함된 YYYY-MM-DD 값을 사용하세요.
- Tool이 반환하지 않은 건강 사실을 추측하지 마세요.
- 의료 진단, 질환 판정, 약물, 치료 방법을 제안하지 마세요.
- 통증이 있으면 운동을 권하지 말고 전문가 확인을 안내하세요.
- 이 단계에서는 계획을 저장하지 말고 반드시 사용자 동의를 요청하세요.
""".strip()

SAVE_INSTRUCTIONS = """
사용자가 직전 행동 계획에 명시적으로 동의했습니다.
직전에 제안한 핵심 행동 한 가지를 save_daily_plan으로 저장하세요.
user_confirmed는 반드시 true로 설정하세요. Tool 결과만 근거로 저장 결과를
한국어로 간결하게 알려주세요. 새로운 건강 계획을 만들지 마세요.
""".strip()


def to_openai_tool(tool) -> dict[str, Any]:
    """MCP Tool Schema를 OpenAI Responses API Function Tool로 변환합니다."""
    raw = tool.model_dump(by_alias=True)
    return {
        "type": "function",
        "name": tool.name,
        "description": tool.description or "",
        "parameters": raw["inputSchema"],
        "strict": False,
    }


def text_result(result) -> str:
    """MCP 응답의 텍스트 콘텐츠를 LLM에 전달할 문자열로 합칩니다."""
    return "\n".join(
        content.text for content in result.content if hasattr(content, "text")
    )


async def execute_tool_calls(session, response, allowed_tools: set[str], trace: list):
    """허용된 MCP Tool만 실행하고 Responses API용 결과를 만듭니다."""
    outputs = []
    for call in response.output:
        if call.type != "function_call":
            continue
        if call.name not in allowed_tools:
            raise PermissionError(f"현재 단계에서 허용되지 않은 Tool입니다: {call.name}")

        arguments = json.loads(call.arguments)
        if not isinstance(arguments, dict):
            raise ValueError("Tool arguments는 JSON Object여야 합니다.")

        # 쓰기 Tool은 실제 사용자 동의를 확인한 이후의 코드 경로에서만 실행됩니다.
        if call.name == "save_daily_plan":
            arguments["user_confirmed"] = True

        result = await session.call_tool(call.name, arguments)
        result_text = text_result(result)
        trace.append(
            {
                "tool": call.name,
                "arguments": arguments,
                "is_error": bool(result.isError),
                "result": result_text,
            }
        )
        outputs.append(
            {
                "type": "function_call_output",
                "call_id": call.call_id,
                "output": result_text,
            }
        )
    return outputs


async def build_proposal(client, session, question: str, tools: list, trace: list):
    """읽기 Tool을 반복 호출해 사용자 동의 전의 계획을 생성합니다."""
    response = await client.responses.create(
        model=OPENAI_MODEL,
        instructions=COACH_INSTRUCTIONS,
        input=question,
        tools=tools,
        parallel_tool_calls=True,
    )

    for _ in range(MAX_TOOL_ROUNDS):
        outputs = await execute_tool_calls(session, response, READ_TOOLS, trace)
        if not outputs:
            called = {item["tool"] for item in trace if item["tool"] in READ_TOOLS}
            missing = READ_TOOLS - called
            if not missing:
                return response
            response = await client.responses.create(
                model=OPENAI_MODEL,
                instructions=COACH_INSTRUCTIONS,
                previous_response_id=response.id,
                input=f"계획 전에 다음 필수 Tool을 호출하세요: {sorted(missing)}",
                tools=tools,
                parallel_tool_calls=True,
            )
            continue
        response = await client.responses.create(
            model=OPENAI_MODEL,
            instructions=COACH_INSTRUCTIONS,
            previous_response_id=response.id,
            input=outputs,
            tools=tools,
            parallel_tool_calls=True,
        )

    raise RuntimeError("계획 생성 중 최대 Tool 호출 횟수를 초과했습니다.")


async def save_proposal(client, session, proposal_response, save_tool: dict, trace: list):
    """승인된 제안을 쓰기 Tool로 저장하고 최종 응답을 생성합니다."""
    response = await client.responses.create(
        model=OPENAI_MODEL,
        instructions=SAVE_INSTRUCTIONS,
        previous_response_id=proposal_response.id,
        input="사용자가 위 계획에 동의했습니다. 승인된 계획을 저장해 주세요.",
        tools=[save_tool],
        tool_choice="required",
    )
    outputs = await execute_tool_calls(session, response, WRITE_TOOLS, trace)
    if not outputs:
        raise RuntimeError("승인 후 save_daily_plan Tool이 호출되지 않았습니다.")
    if trace[-1]["is_error"]:
        raise RuntimeError(f"계획 저장에 실패했습니다: {trace[-1]['result']}")

    return await client.responses.create(
        model=OPENAI_MODEL,
        instructions=SAVE_INSTRUCTIONS,
        previous_response_id=response.id,
        input=outputs,
    )


async def answer(question: str) -> dict[str, Any]:
    """비대화형 API: 읽기 Tool로 계획을 만들고 승인 대기 상태로 반환합니다."""
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY가 필요합니다.")

    trace: list[dict[str, Any]] = []
    async with AsyncOpenAI() as client, connect_to_health_coach_server() as session:
        discovered = (await session.list_tools()).tools
        by_name = {tool.name: to_openai_tool(tool) for tool in discovered}
        missing = (READ_TOOLS | WRITE_TOOLS) - by_name.keys()
        if missing:
            raise RuntimeError(f"MCP Server에 필요한 Tool이 없습니다: {sorted(missing)}")

        read_tools = [by_name[name] for name in sorted(READ_TOOLS)]
        proposal = await build_proposal(client, session, question, read_tools, trace)
        return {
            "question": question,
            "model": OPENAI_MODEL,
            "discovered_tools": sorted(by_name),
            "proposal": proposal.output_text,
            "approved": False,
            "status": "waiting_for_approval",
            "trace": trace,
        }


async def interactive_main() -> None:
    """터미널에서 계획 제안과 사람 승인을 순서대로 실행합니다."""
    today = date.today().isoformat()
    question = (
        f"demo-user의 {today} 건강 습관 계획을 만들어 주세요. "
        "오늘 실천할 핵심 행동 한 가지만 제안해 주세요."
    )

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY가 필요합니다.")

    trace: list[dict[str, Any]] = []
    async with AsyncOpenAI() as client, connect_to_health_coach_server() as session:
        discovered = (await session.list_tools()).tools
        by_name = {tool.name: to_openai_tool(tool) for tool in discovered}
        missing = (READ_TOOLS | WRITE_TOOLS) - by_name.keys()
        if missing:
            raise RuntimeError(f"MCP Server에 필요한 Tool이 없습니다: {sorted(missing)}")

        read_tools = [by_name[name] for name in sorted(READ_TOOLS)]
        proposal = await build_proposal(client, session, question, read_tools, trace)
        print("\n[오늘의 제안]\n")
        print(proposal.output_text)

        approval = input(
            "\n이 계획을 저장하고 알림을 예약할까요? [y/N]: "
        ).strip().lower()
        if approval not in {"y", "yes", "예", "네"}:
            print("계획을 저장하지 않았습니다.")
            return

        saved = await save_proposal(
            client, session, proposal, by_name["save_daily_plan"], trace
        )
        print("\n[저장 결과]\n")
        print(saved.output_text)
        print("\n[Tool Trace]\n")
        print(json.dumps(trace, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(interactive_main())
