# 분석 후속 대화 (Analysis Chat) — 설계 스펙

- 작성일: 2026-05-08
- 대상 PR(2개로 분리):
  - **PR-1**: LangChain 1.x 의존성 일제 업그레이드 + 기존 분석 그래프 회귀 통과
  - **PR-2**: 본 스펙의 채팅 기능 구현
- 전제: PR-1 머지 후 PR-2 시작.

## 1. 목적

분석이 `completed` 상태로 끝난 뒤, 사용자가 그 결과(7개 리포트 + 결정/신뢰도)를 바탕으로 어시스턴트와 후속 대화를 이어갈 수 있게 한다. 어시스턴트는 분석 그래프가 사용한 도구(가격·지표·펀더멘털·뉴스 등)를 모두 호출할 수 있으며, 응답은 SSE 토큰 스트리밍으로 실시간 렌더된다. 대화는 분석별로 영구 저장된다.

## 2. 사용자 흐름

| 분석 상태 | 채팅 섹션 동작 |
|---|---|
| `completed` | 정상 활성. history/[id] 하단에 인라인 섹션. |
| `running` | history 페이지가 `/run/[id]`로 redirect → 채팅 노출 없음. |
| `failed` / `cancelled` | 채팅 섹션 비활성 — "이 분석은 완료되지 않아 후속 대화를 할 수 없어요" 안내 카드. `final_state` 보유 여부와 무관. |

채팅 도중 LLM/도구 실패 시: 그 시점까지 받은 토큰을 `partial=true, error=<msg>`로 영속화하고 입력창을 즉시 재활성. 사용자는 새 메시지를 입력해 대화를 이어갈 수 있다. 사용자가 "중지" 버튼을 눌러 끊은 경우는 `cancelled=true`로 표시(에러 표기 없음).

**재시도 규칙**: 부분/취소된 응답을 이어붙이지 않는다. 사용자가 다음 메시지를 보내면 새 `turn_id`로 진행되며, 슬라이딩 윈도우 컨텍스트(§ 3.2)에 직전 partial/cancelled 메시지도 포함되어 모델이 "방금 끊겼다"는 맥락을 인지한다.

## 3. 데이터 모델

새 테이블 1개 (`chat_messages`). `analyses` 스키마는 변경하지 않는다.

### 3.1 `tradingagents_web/models/chat_message.py`

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `id` | int PK | |
| `analysis_id` | int FK → `analyses.id` | NOT NULL, indexed |
| `turn_id` | str(36) UUID | indexed. 한 사용자 메시지 → assistant 응답(+tool 호출 세트)을 묶는 키. 재시도 시 새 turn. |
| `sequence` | int | NOT NULL. `(analysis_id, sequence)` UNIQUE. |
| `role` | str(16) | `user` \| `assistant` \| `tool` |
| `content_blocks` | JSON | LangChain 1.x `content_blocks` 표준 — text/reasoning/tool_use/tool_result/image 블록 배열. |
| `tool_calls` | JSON nullable | `role=assistant`가 도구 호출 시. `[{name, args, id}]`. |
| `tool_call_id` | str(64) nullable | `role=tool`이 어느 호출에 응답하는지. |
| `tool_name` | str(64) nullable | `role=tool` 라벨링/필터링용. |
| `partial` | bool default false | 스트리밍이 끝나기 전에 끊긴 어시스턴트 메시지. |
| `cancelled` | bool default false | 사용자 중지 버튼으로 끊김. |
| `error` | str(2048) nullable | `partial=true`일 때 에러 요약. |
| `cost_usd` | float nullable | `role=assistant` 한 응답의 LLM 비용. |
| `model_id` | str(64) nullable | 응답에 쓰인 모델 식별자(분석 deep 모델). |
| `created_at` | datetime tz | |
| `completed_at` | datetime tz nullable | 어시스턴트 메시지 종료 시각. |

**인덱스**: `(analysis_id, sequence)` UNIQUE, `turn_id`.

### 3.2 컨텍스트 윈도우 정책

- 분석 결과 컨텍스트(고정, system_prompt에 주입) + 최근 `N=8` `turn_id`에 속한 모든 메시지(user/assistant/tool)를 시간순으로 LLM 입력으로 사용.
- 미들웨어로 `SummarizationMiddleware`(§ 7) 적용 → 토큰 한계 도달 시 오래된 부분만 요약으로 압축. 영속 데이터(DB)는 원문 유지.

### 3.3 스트리밍 영속화 정책

- 사용자 메시지: 받자마자 즉시 commit(중복 전송 방지 + reconnect 시 echo 보장).
- 어시스턴트 응답 + 동반 tool 메시지: 메모리 버퍼에서 누적 → 종료(완료/에러/중지) 시점에 단일 트랜잭션으로 flush.

### 3.4 마이그레이션

- alembic 새 revision 1개: `add_chat_messages_table`.
- `analyses` 변경 없음.

## 4. 백엔드 모듈 / API

### 4.1 신규 파일

```
tradingagents_web/
├── api/chat.py                     # 라우트
├── models/chat_message.py
├── schemas/chat.py
├── services/
│   ├── chat_runner.py              # create_agent + astream
│   ├── chat_context.py             # system_prompt + history 빌더
│   └── chat_tools.py               # 도구 export 묶음
migrations/versions/XXXX_add_chat_messages.py
```

기존 `services/event_bus.py`는 채널 키만 `chat:{run_id}:{turn_id}`로 바꿔 재사용.

### 4.2 엔드포인트 (`/api/runs/{run_id}/chat/...`)

| 메서드 | 경로 | 용도 |
|---|---|---|
| `GET` | `/messages` | 영속 메시지 페이지네이션. |
| `POST` | `/turns` | 사용자 메시지 + 어시스턴트 백그라운드 turn 시작. 응답: `{turn_id}`. |
| `GET` | `/turns/{turn_id}/stream` | SSE 이벤트 스트림. |
| `DELETE` | `/turns/{turn_id}` | 진행 중 turn 중지. |

권한: 기존 `get_current_user` + `require_xhr`. 단일 사용자 self-host 전제이므로 분석 소유자 검증 불필요(`User`는 1행만 존재).

### 4.3 `chat_runner._execute_turn` 핵심 흐름

```python
async def _execute_turn(run_id, analysis_id, turn_id):
    bus = get_event_bus()
    channel = f"chat:{run_id}:{turn_id}"
    db = _session_factory()
    full_message = None
    tool_messages = []
    try:
        analysis = db.query(Analysis).filter_by(id=analysis_id).one()
        history = build_message_history(db, analysis_id, window_n=8)
        agent = create_agent(
            model=resolve_chat_model(analysis),
            tools=get_chat_tools(analysis),
            system_prompt=build_system_prompt(analysis),
            middleware=[summarization_middleware(analysis)],
        )
        async for chunk in agent.astream(
            {"messages": history},
            stream_mode=["messages", "updates"],
            version="v2",
        ):
            # token / tool_call / tool_result 이벤트로 매핑하여 bus.publish
            ...
        _persist_turn(db, analysis_id, turn_id, full_message, tool_messages)
        bus.publish(channel, ChatEvent(type="done", data={...}))
    except asyncio.CancelledError:
        _persist_partial_turn(..., cancelled=True, error=None)
        bus.publish(channel, ChatEvent(type="cancelled", data={}))
        raise
    except Exception as exc:
        _persist_partial_turn(..., partial=True, error=str(exc))
        bus.publish(channel, ChatEvent(type="error", data={"message": str(exc)}))
    finally:
        bus.publish(channel, ChatEvent(type="close", data={}))
        bus.finish(channel)
        _RUNNING_TURNS.pop(turn_id, None)
        db.close()
```

## 5. SSE 이벤트 프로토콜

`agent.astream(..., stream_mode=["messages","updates"], version="v2")` 청크를 다음 이벤트로 매핑:

| event | 발생 시점 | data 페이로드 |
|---|---|---|
| `token` | `chunk.type=="messages"` & `AIMessageChunk.text` | `{"text": "...", "block_index": 0}` |
| `tool_call` | tool_call_chunks 누적 완성 또는 updates의 model 노드 | `{"id", "name", "args"}` |
| `tool_result` | updates의 `source=="tools"` ToolMessage | `{"tool_call_id", "name", "content_blocks", "ok", "duration_ms"}` |
| `done` | astream 정상 종료 + DB flush 완료 | `{"sequence_start", "sequence_end", "cost_usd", "model"}` |
| `error` | astream 중 예외 또는 실패 | `{"message", "partial": true}` |
| `cancelled` | DELETE 호출로 중지 | `{}` |
| `close` | 모든 상황의 마지막 1회 | `{}` |

- 모든 이벤트에 `id`(누적 seq) 동봉 → `Last-Event-ID` 재연결로 누락 보충.
- 헤더: `Cache-Control: no-cache`, `X-Accel-Buffering: no`.
- 채널 키: `chat:{run_id}:{turn_id}`.
- 종료 보장: 어떤 경로에서든 `error|done|cancelled` 중 1개 + `close`를 emit하고 finish 마킹.
- in-memory 버퍼는 finish 후 60초 유지.
- POST 직후 SSE 접속해도 누락되지 않도록 task 시작 직전 `bus.prime(channel)`.

## 6. 도구 정의 + 시스템 프롬프트

### 6.1 도구 (`services/chat_tools.py`)

기존 `tradingagents/agents/utils/agent_utils.py`에서 export되는 9개 도구를 그대로 재사용:
- `get_stock_data`, `get_indicators`
- `get_fundamentals`, `get_balance_sheet`, `get_cashflow`, `get_income_statement`
- `get_news`, `get_insider_transactions`, `get_global_news`

이미 `@tool` 데코레이터로 LangChain 1.x 호환. `from langchain.tools import tool` 경로로 통일(구 `langchain_core.tools.tool`은 alias).

### 6.2 시스템 프롬프트 (`services/chat_context.py`)

```
당신은 TradingAgents가 수행한 분석 결과를 바탕으로 후속 질문에 답하는 한국어 어시스턴트입니다.

## 분석 메타
- 종목: {ticker}
- 분석일: {analysis_date}
- 결정: {decision} (신뢰도 {confidence})
- 사용 모델: {provider} / deep={deep_model}

## 도구 사용 규칙
- 분석 당시 데이터로 답할 수 있으면 도구를 호출하지 말고 본문 컨텍스트로 답하세요.
- 사용자가 "지금", "최신", "오늘" 같은 표현으로 새 데이터를 요구하면 도구를 호출하세요.
- 도구 호출 시 ticker 기본은 "{ticker}", 분석 기준일은 "{analysis_date}"입니다.
- 한 번의 응답에서 동일 도구를 같은 인자로 두 번 호출하지 마세요.

## 응답 스타일
- 한국어로 답하세요. 사용자가 영어로 물어도 한국어 우선.
- 결정에 대한 근거를 묻는 질문에는 위 컨텍스트의 해당 섹션을 인용해 설명하세요.
- 추측이 필요한 경우 "분석 시점 데이터 기준" 같은 단서를 명시하세요.

## 분석 본문 (참고용 컨텍스트)
{각 리포트를 ## 섹션 헤딩으로 결합}
```

## 7. SummarizationMiddleware (LangChain 1.x)

```python
from langchain.agents.middleware import SummarizationMiddleware

SummarizationMiddleware(
    model=quick_model_instance,         # 분석 quick 모델 재사용 (비용 ↓)
    trigger=("fraction", 0.7),           # 모델 컨텍스트의 70% 도달 시
    keep=("messages", 12),               # 최근 12개 메시지(≈6턴) 원문 유지
    summary_prompt=KO_SUMMARY_PROMPT,    # 한국어/투자 후속 대화 톤
)
```

`KO_SUMMARY_PROMPT`는 한국어 불릿 5~8개로 사실 위주 요약(반복 질문/관심사, 도구 호출 결과 핵심 수치, 합의된 결론). 추측·해석 금지.

영속 저장은 미들웨어와 무관 — DB에는 원문 메시지가 그대로 남고, 미들웨어의 요약은 LLM 입력 단계에서만 일어나는 ephemeral 변환.

## 8. 모델 해석

```python
def resolve_chat_model(analysis: Analysis) -> BaseChatModel:
    client = create_llm_client(
        provider=analysis.llm_provider,
        model=analysis.llm_deep_model,
    )
    return client.get_llm()
```

`create_agent(model=...)`은 `BaseChatModel` 인스턴스를 직접 받는다(문자열 단축 표기 미사용 → 기존 factory 재사용).

## 9. 프론트엔드

### 9.1 신규 파일

```
web/
├── lib/
│   ├── chat.ts                     # 타입 + REST 클라이언트
│   └── chat-sse.ts                 # openChatStream
├── hooks/
│   ├── use-chat-messages.ts
│   ├── use-chat-stream.ts
│   └── use-create-chat-turn.ts
└── components/chat/
    ├── chat-section.tsx            # history detail 하단에 삽입
    ├── chat-message.tsx
    ├── chat-tool-call.tsx          # 토글 카드
    └── chat-input.tsx
```

### 9.2 통합

`web/app/(workspace)/history/[id]/page.tsx` 하단에 조건부 렌더:

```tsx
{a.status === "completed"
  ? <ChatSection runId={id} />
  : <Card><CardContent>
      <p className="text-xs text-text-3">
        이 분석은 완료되지 않아 후속 대화를 할 수 없어요.
      </p>
    </CardContent></Card>}
```

### 9.3 도구 호출 토글 UI

기본 접힘. 펼치면 args + result 원문(`<pre>`). 상태 아이콘:
- 🌀 실행 중 (`tool_call`만 받고 `tool_result` 미수신)
- ✓ 완료 (`tool_result.ok=true`)
- ❌ 실패 (`tool_result.ok=false`)

### 9.4 use-chat-stream 누적 규칙

- `tokensByBlock: Record<number, string>` — block_index 별 누적
- `toolCalls: { id, name, args, status, result? }[]`
- `done`/`error`/`cancelled` 종료 플래그 + React Query invalidate(`chat-messages` 갱신)
- `close` 이벤트에서 ES 종료
- 자동 재연결: EventSource 기본 동작 + 60초 서버 버퍼

### 9.5 메시지 카드 렌더 우선순위

1. tool_calls 있으면 위에 ChatToolCall 카드들(순서대로)
2. 본문 텍스트 (기존 `MarkdownText` 재사용)
3. partial인 경우 빨간 톤 안내 + "다시 시도" 버튼
4. 푸터 메타: model · cost

## 10. 에러 / 취소 / 동시성

### 10.1 실패 매트릭스

| 시점 | 서버 | 클라이언트 |
|---|---|---|
| POST 시 분석이 not completed | 409 | 입력창 비활성 + 토스트 |
| POST 시 진행 중 turn 존재 | 409 | 진행 중 메시지 종료까지 입력 disable |
| LLM 클라이언트 생성 실패 | 빈 assistant 메시지 1개 + error SSE | 빨간 안내 카드, 입력창 활성 |
| astream 진행 중 예외 | 부분 누적분 partial=true 영속 + error SSE | 토글 표시 유지, 본문 빨간 안내, 입력창 활성 |
| DELETE 중지 | 부분 누적분 cancelled=true 영속 + cancelled SSE | 본문 회색 안내, 입력창 활성 |
| SSE 끊김 | task 계속, 종료 시 정상 영속 | EventSource 자동 재연결 + 60초 윈도우 |
| 페이지 이탈 | task 계속 → 정상 영속 | 재진입 시 영속 메시지로 복원 |
| 서버 재시작 | in-memory 부분 메시지 유실 | 사용자 메시지만 남고 짝 없는 turn 감지 → 안내 + 재전송 유도 |

### 10.2 취소 시그널

- `_RUNNING_TURNS: dict[str, asyncio.Task]`에 task 보관.
- DELETE 핸들러에서 `task.cancel()`.
- `_execute_turn`은 `asyncio.CancelledError` catch → 부분 영속 + `cancelled` 이벤트 → re-raise.

### 10.3 동시성 가드

- 한 분석에 동시 진행 중 turn 최대 1개. POST 시점에 진행 중 turn(`_RUNNING_TURNS` 또는 짝 안 맞는 user 메시지) 감지 시 409.
- 분석 간 동시 채팅 허용(채널 키 분리).

### 10.4 도구 호출 실패

- 한 도구 호출 실패는 turn 전체 실패가 아님(LangGraph가 ToolMessage로 감싸 모델에 전달).
- SSE에서 `tool_result.ok=false`로 표기. UI는 ❌ 아이콘만 추가.

### 10.5 크기 가드

- 사용자 메시지 길이 상한 8,000자(서버 422 + 클라이언트 maxLength).
- 도구 결과 본문은 분석 그래프에서 이미 검증된 형태 그대로.

## 11. 테스트 계획

### 11.1 백엔드 (pytest)

- **test_chat_models.py**: ORM/스키마/마이그레이션 round-trip
- **test_chat_context.py**: build_system_prompt(완전·부분 final_state), build_message_history 슬라이딩 윈도우
- **test_chat_runner.py** (핵심): `create_agent`를 stub으로 패치, 다음 케이스
  1. 단순 응답 (도구 없음)
  2. 도구 호출 1회
  3. 도구 호출 다회 연쇄
  4. 도구 호출 실패
  5. astream RuntimeError → partial=true 영속
  6. asyncio.CancelledError → cancelled=true 영속
- **test_chat_api.py**: 인증/CSRF/상태별 409, 페이지네이션, SSE 헤더, 중지
- **test_chat_event_bus.py**: 채널 격리, Last-Event-ID 재연결, 60초 버퍼

### 11.2 프론트엔드

- **lib/chat.test.cjs**: 타입/직렬화 round-trip
- **hooks/use-chat-stream.test.tsx**: Mock EventSource로 token/tool_call/tool_result/done 시퀀스 주입, 누적/상태 전이 검증

### 11.3 회귀

- 분석 그래프(`tradingagents/graph/trading_graph.py`) 기존 e2e 테스트 통과 (PR-1에서 검증, PR-2에서도 재확인).

### 11.4 브라우저 자동화 E2E (Playwright MCP)

`tests/e2e/chat.spec.ts` 신설. dev 서버에 붙어서 자동 실행:

- 로그인 → completed 분석 진입 → 채팅 섹션 노출
- 단순 질문 → 토큰 점진 렌더 + done 메타 표시
- 도구 호출 유발 질문 → tool_call 라벨 🌀→✓ 토글, 펼치면 args/result
- 중지 버튼 → 회색 안내 + 입력창 재활성
- 새로고침 → 대화 복원
- failed/cancelled 분석 진입 → 비활성 안내
- 모바일 뷰포트(375x667) 레이아웃
- LLM 키 일시 제거 시 빨간 안내 + 부분 영속 + 재시도

CI는 이번 PR에선 수동 트리거(`npx playwright test`).

### 11.5 수동 점검 체크리스트

위 11.4와 동일 시나리오. 머지 전 reviewer가 로컬에서 1회 실행.

### 11.6 커버리지 목표

CLAUDE.md 기준 90% 이상. LangChain 외부 호출은 테스트 더블로 대체.

## 12. 롤아웃

### 12.1 PR 분리

- **PR-1 (선행)**: LangChain 1.x 의존성 일제 업그레이드
  - `langchain>=1.0`, `langchain-core>=1.0`, `langchain-openai>=1.0`, `langchain-anthropic>=1.0`, `langchain-google-genai`(1.x 호환), `langgraph>=1.0`
  - 코드 변경 최소(import alias로 호환). deprecation 경고만 정리.
  - 회귀: 분석 그래프 e2e + CLI(`cli/main.py`) + 웹 분석 1회 실행.
- **PR-2 (본 스펙)**: 채팅 기능 구현 + alembic 마이그레이션 + 새 라우터 등록(`tradingagents_web/main.py`).

### 12.2 적용 순서

1. PR-1 머지 → `uv sync`
2. PR-2 머지 → `alembic upgrade head` (`chat_messages` 생성)
3. 기존 분석 자동 채팅 가능

### 12.3 새 ENV 없음

모델/프로바이더는 분석 row 값을 그대로 사용. 다음 상수는 코드에 둠(향후 ENV 오버라이드 여지):
- `CHAT_TURN_WINDOW=8`
- `SUMMARY_TRIGGER_FRACTION=0.7`
- `SUMMARY_KEEP_MESSAGES=12`
- `SSE_RECONNECT_BUFFER_SECONDS=60`
- `USER_MESSAGE_MAX_CHARS=8000`

### 12.4 운영

- 백그라운드 task는 `_RUNNING_TURNS` 강한 참조 + done_callback에서 정리(기존 `runs.py` 패턴).
- 별도 큐/워커 없음(self-host 단일 사용자, 동시 turn 1개).

## 13. 범위 외 (Future work)

- 분석별 비용 누적 표시 / 일일 비용 한도
- 다중 사용자 확장 (analyses/chat_messages에 user_id FK 추가 필요)
- 채팅 export(마크다운 다운로드)
- 도구 결과 자동 차트 시각화
- reasoning 블록 별도 토글(OpenAI Responses / Anthropic thinking)
- Playwright CI 자동 실행
