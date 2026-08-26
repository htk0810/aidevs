"""개인화 건강 습관 코치용 stdio MCP Server.

교육용 MVP이므로 외부 건강 API 대신 메모리 데이터를 사용합니다. Tool의 입력과
출력 계약은 실제 건강 기록, 캘린더, 날씨, 알림 API로 교체해도 유지할 수 있습니다.
의료 진단이나 처방은 제공하지 않습니다.
"""

from datetime import date as date_type
from typing import Literal
from uuid import uuid4

from mcp.server.fastmcp import FastMCP


mcp = FastMCP(
    "personal-health-habit-coach",
    instructions=(
        "식단·운동·수면 습관을 위한 교육용 도구입니다. 의료 진단, 처방, "
        "치료 추천에 사용하지 마세요. 계획 저장은 사용자의 명시적 동의 후에만 "
        "허용됩니다."
    ),
)


HEALTH_RECORDS = {
    "demo-user": {
        "goal": "체력 향상과 규칙적인 수면",
        "sleep": {
            "average_hours": 6.2,
            "target_hours": 7.0,
            "late_bedtime_days": 3,
        },
        "exercise": {
            "completed_days": 2,
            "target_days": 4,
            "preferred_intensity": "light",
        },
        "meal": {
            "breakfast_skip_days": 3,
            "late_dinner_days": 2,
        },
    }
}


DAILY_CONTEXT = {
    "demo-user": {
        "available_time_minutes": 30,
        "available_time_ranges": ["19:00-20:00"],
        "condition": {"energy": 3, "stress": 4, "pain": False},
        "weather": {
            "condition": "비",
            "outdoor_activity_recommended": False,
        },
    }
}


SAVED_PLANS: list[dict] = []


def _require_user(user_id: str) -> str:
    normalized = user_id.strip()
    if normalized not in HEALTH_RECORDS:
        raise ValueError(f"건강 기록을 찾을 수 없는 사용자입니다: {normalized}")
    return normalized


def _require_iso_date(value: str) -> str:
    if len(value) != 10 or value[4] != "-" or value[7] != "-":
        raise ValueError("date는 YYYY-MM-DD 형식이어야 합니다.")
    try:
        return date_type.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise ValueError("date는 YYYY-MM-DD 형식이어야 합니다.") from exc


def _require_time(value: str) -> str:
    parts = value.split(":")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        raise ValueError("scheduled_time은 HH:MM 형식이어야 합니다.")
    hour, minute = map(int, parts)
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("scheduled_time이 올바른 시간이 아닙니다.")
    return f"{hour:02d}:{minute:02d}"


@mcp.tool()
def get_health_summary(user_id: str, days: int = 7) -> dict:
    """사용자의 목표와 최근 식단·운동·수면 습관을 요약합니다."""
    normalized = _require_user(user_id)
    if not 1 <= days <= 30:
        raise ValueError("days는 1~30이어야 합니다.")

    record = HEALTH_RECORDS[normalized]
    return {
        "user_id": normalized,
        "period_days": days,
        **record,
        "data_quality": {
            "source": "demo-health-records",
            "is_demo_data": True,
        },
    }


@mcp.tool()
def get_daily_context(user_id: str, date: str) -> dict:
    """계획할 날짜의 여유 시간, 컨디션, 날씨를 조회합니다."""
    normalized = _require_user(user_id)
    normalized_date = _require_iso_date(date)
    context = DAILY_CONTEXT[normalized]
    return {
        "user_id": normalized,
        "date": normalized_date,
        **context,
        "data_quality": {
            "source": "demo-calendar-checkin-weather",
            "is_demo_data": True,
        },
    }


@mcp.tool()
def save_daily_plan(
    user_id: str,
    date: str,
    action_type: Literal["sleep", "exercise", "meal"],
    action: str,
    scheduled_time: str,
    duration_minutes: int,
    user_confirmed: bool,
) -> dict:
    """명시적으로 동의한 하루 행동 계획을 저장하고 알림을 예약합니다."""
    normalized = _require_user(user_id)
    normalized_date = _require_iso_date(date)
    normalized_time = _require_time(scheduled_time)

    if not user_confirmed:
        raise PermissionError("사용자의 명시적 동의 없이는 계획을 저장할 수 없습니다.")
    if not action.strip():
        raise ValueError("action은 빈 문자열일 수 없습니다.")
    if not 5 <= duration_minutes <= 120:
        raise ValueError("duration_minutes는 5~120이어야 합니다.")

    plan = {
        "plan_id": f"plan-{uuid4().hex[:8]}",
        "user_id": normalized,
        "date": normalized_date,
        "action_type": action_type,
        "action": action.strip(),
        "scheduled_time": normalized_time,
        "duration_minutes": duration_minutes,
        "status": "scheduled",
    }
    SAVED_PLANS.append(plan)
    return {
        "saved": True,
        "plan": plan,
        "notification": {
            "scheduled": True,
            "channel": "demo-notification",
            "message": f"{normalized_time}에 {action.strip()} 계획이 있습니다.",
        },
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
