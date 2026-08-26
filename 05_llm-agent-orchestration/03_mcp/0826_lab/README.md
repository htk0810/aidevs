# 개인화 건강 습관 코치 AI Agent

사용자의 최근 식단·운동·수면 기록과 오늘의 일정·컨디션·날씨를 바탕으로
실천 가능한 행동 한 가지를 제안하는 MCP 기반 교육용 MVP입니다.

의료 진단, 질환 판정, 처방 또는 치료 추천은 제공하지 않습니다.

## 구성

```text
사용자 요청
   ↓
AI Agent
   ├─ get_health_summary: 최근 습관과 목표 조회
   ├─ get_daily_context: 오늘 일정·컨디션·날씨 조회
   ↓
LLM이 행동 계획 한 가지 제안
   ↓
사용자 승인
   ↓
save_daily_plan: 계획 저장 및 데모 알림 예약
```

| 파일 | 역할 |
|---|---|
| `mcp_server.py` | 세 개의 건강 습관 MCP Tool과 데모 데이터 제공 |
| `_stdio_client.py` | MCP Server를 자식 프로세스로 실행하고 연결 |
| `ai_agent.py` | Tool 선택, 계획 생성, 사람 승인, 저장 흐름 관리 |

## MCP Tool

### `get_health_summary`

`user_id`와 최근 조회 기간을 받아 식단·운동·수면 기록과 목표를 반환합니다.

### `get_daily_context`

`user_id`와 날짜를 받아 여유 시간, 컨디션, 날씨를 반환합니다.

### `save_daily_plan`

사용자가 승인한 핵심 행동 한 가지를 저장하고 데모 알림을 예약합니다.
`user_confirmed=true`가 아니면 서버에서 거부합니다.

## 실행 준비

과정 루트의 `.env`에 다음 값을 설정합니다.

```dotenv
OPENAI_API_KEY=your-api-key
OPENAI_MODEL=gpt-4.1-mini
```

과정 루트 가상환경에 의존성을 설치합니다.

```powershell
cd C:\aidevs\05_llm-agent-orchestration
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 실행

현재 폴더에서 실행합니다.

```powershell
..\..\.venv\Scripts\python.exe .\ai_agent.py
```

Agent는 `demo-user`의 당일 계획을 제안한 뒤 다음과 같이 승인을 요청합니다.

```text
이 계획을 저장하고 알림을 예약할까요? [y/N]:
```

- `y`, `yes`, `예`, `네`: 승인한 계획을 저장합니다.
- 그 외 입력: 아무것도 저장하지 않고 종료합니다.

읽기 단계에는 `save_daily_plan` Tool 자체를 LLM에 제공하지 않습니다. 승인 후에만
쓰기 Tool을 공개하며, MCP Server도 `user_confirmed`를 다시 검사합니다.

## MCP 스모크 테스트

OpenAI API를 호출하지 않고 Tool 발견, 데이터 조회, 미승인 저장 거부, 승인 저장을
검증할 수 있습니다.

```powershell
..\..\.venv\Scripts\python.exe .\smoke_test.py
```

## 현재 데이터와 확장 지점

현재 `mcp_server.py`의 메모리 데이터는 외부 서비스 없이 Agent 흐름을 검증하기
위한 데모입니다. Tool의 입출력 형태를 유지하고 내부 구현을 다음과 같이 교체할
수 있습니다.

| 현재 구현 | 확장 대상 |
|---|---|
| `HEALTH_RECORDS` | 건강 기록 DB, Health Connect, Fitbit 등 |
| `DAILY_CONTEXT` | Google/Outlook Calendar, 날씨, 미세먼지, 체크인 |
| `SAVED_PLANS` | 계획 DB, 캘린더, 푸시 알림 서비스 |

RAG가 필요해지면 검증된 공공기관 생활 습관 지침만 검색하는
`search_health_guidance` Tool을 별도로 추가합니다. 개인 건강 기록과 일반 지식
문서는 서로 다른 저장소와 권한 정책으로 관리하는 것이 좋습니다.

## 안전 원칙

- 사용자가 보지 않은 계획은 저장하지 않습니다.
- 저장 전 명시적 승인을 받습니다.
- 통증이 보고되면 운동을 권하지 않도록 Agent 지침을 적용합니다.
- 의료 진단·처방·치료 추천을 하지 않습니다.
- 실제 서비스에서는 사용자 인증, 최소 권한, 암호화, 감사 로그가 추가로 필요합니다.
