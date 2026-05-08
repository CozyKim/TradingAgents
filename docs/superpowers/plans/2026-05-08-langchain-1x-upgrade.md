# LangChain 1.x 의존성 업그레이드 (PR-1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 분석 후속 대화 기능(PR-2)이 사용할 LangChain 1.x 라인으로 의존성을 일제 업그레이드하고, 기존 분석 그래프/CLI/웹 분석 흐름이 그대로 동작함을 회귀 테스트로 검증한다.

**Architecture:** 코드 변경 최소. `pyproject.toml`의 langchain 계열 패키지 minor를 1.x로 올리고 `uv lock`/`uv sync`로 잠금. import 경로 변경 없이 alias로 동작하는지 확인. deprecation 경고가 뜨는 곳만 좁게 정리.

**Tech Stack:** uv, langchain 1.x, langgraph 1.x, langchain-openai/-anthropic/-google-genai 신버전, pytest

**Spec:** `docs/superpowers/specs/2026-05-08-analysis-chat-design.md` § 0, § 12.1

---

### Task 1: 의존성 버전 변경

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: 현재 langchain 계열 의존성 확인**

Run: `grep -n "langchain\|langgraph" pyproject.toml`
Expected: 6줄 (langchain-anthropic, langchain-core, langchain-experimental, langchain-google-genai, langchain-openai, langgraph)

- [ ] **Step 2: 버전 변경**

`pyproject.toml`의 `dependencies` 블록을 다음으로 갱신(다른 줄은 손대지 않음):

```toml
    "langchain>=1.0",
    "langchain-anthropic>=1.0",
    "langchain-core>=1.0",
    "langchain-experimental>=1.0",
    "langchain-google-genai>=3.0",
    "langchain-openai>=1.0",
    "langgraph>=1.0",
```

기존에 `langchain` 패키지 자체가 deps에 없을 수 있다 — `langchain-core`만 있을 가능성이 높음. 1.x에서는 `langchain.agents.create_agent`/`langchain.agents.middleware`를 쓰므로 **루트 `langchain>=1.0` 추가는 필수**.

- [ ] **Step 3: lock 갱신**

Run: `uv lock`
Expected: lockfile 갱신, 충돌 없음. 충돌 메시지가 나오면 해당 패키지의 1.x 호환 버전을 검색해 `>=` 하한을 조정.

- [ ] **Step 4: 환경 동기화**

Run: `uv sync`
Expected: 패키지 다운그레이드/업그레이드 결과 출력. 마지막에 `Bytecode compiled` 또는 `Resolved` 표시.

- [ ] **Step 5: import smoke test**

Run:
```bash
uv run python -c "
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain.messages import HumanMessage, AIMessage, ToolMessage, AIMessageChunk
from langchain.tools import tool
import langgraph
print('langchain', __import__('langchain').__version__)
print('langgraph', langgraph.__version__)
"
```
Expected: 두 줄 모두 `1.x` 출력, 어떤 import도 ImportError 없음.

- [ ] **Step 6: 커밋**

```bash
git add pyproject.toml uv.lock
git commit -m "chore(deps): langchain 1.x 라인으로 의존성 업그레이드"
```

---

### Task 2: 분석 그래프 import 회귀 확인

**Files:**
- Read: `tradingagents/graph/trading_graph.py`
- Read: `tradingagents/agents/utils/agent_utils.py`
- Read: `tradingagents/agents/utils/core_stock_tools.py` (외 도구 파일들)

- [ ] **Step 1: 모듈 import smoke**

Run:
```bash
uv run python -c "
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.agents.utils.agent_utils import (
    get_stock_data, get_indicators, get_fundamentals,
    get_balance_sheet, get_cashflow, get_income_statement,
    get_news, get_insider_transactions, get_global_news,
)
print('graph + 9 tools imported OK')
"
```
Expected: `graph + 9 tools imported OK`. ImportError 또는 DeprecationWarning은 stderr로 보일 수 있음.

- [ ] **Step 2: deprecation 경고 정리(있을 때만)**

`uv run python -W error::DeprecationWarning -c "..."`로 다시 돌렸을 때 에러가 뜨면, 메시지가 가리키는 파일을 열어서 권장 import 경로로 한 줄만 수정. 예:
- `from langchain_core.messages import HumanMessage` → 그대로 동작(alias). 변경 불필요.
- `from langchain_core.tools import tool` → `from langchain.tools import tool`로 옮길 수 있으나 PR-2에서 다룸. PR-1에서는 **에러로 승격되는 deprecation만** 정리.

만약 수정한 파일이 있으면 이 step에서 함께 커밋.

- [ ] **Step 3: 인스턴스화 smoke**

Run:
```bash
uv run python -c "
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph
g = TradingAgentsGraph(
    selected_analysts=['market'],
    config=DEFAULT_CONFIG,
    debug=False,
)
print('TradingAgentsGraph constructed OK')
"
```
Expected: `TradingAgentsGraph constructed OK`. 이는 LLM 호출 없이 그래프 구성만 검증.

- [ ] **Step 4: 커밋(수정이 있었을 때만)**

```bash
git add -p   # deprecation 정리 라인만
git commit -m "fix: langchain 1.x deprecation import 경로 정리"
```
수정이 없었으면 이 step은 skip.

---

### Task 3: pytest 회귀 통과

**Files:**
- Run: `tests/`

- [ ] **Step 1: 기존 테스트 슈트 실행**

Run: `uv run pytest -x -q`
Expected: 기존 테스트가 모두 PASS 또는 SKIP. 실패가 나면 스택을 읽고 1.x 시그니처 변화로 인한 실패면 좁게 수정.

- [ ] **Step 2: 실패가 있으면 좁은 수정**

자주 발생하는 패턴:
- `agent.invoke({"input": ...})` → 1.x에선 `{"messages": [...]}` 입력. 기존 코드가 `langgraph.prebuilt.create_react_agent`를 직접 쓰던 곳에서 발생 가능.
- `langchain.chat_models.ChatOpenAI` → 1.x도 alias 유지. 변경 불필요.
- `from langchain_core.runnables import RunnableConfig` → 그대로 동작.

수정은 **테스트 또는 호출부 한 곳만** 손대고, 호출 시그니처 변경이 광범위하면 PR-1 범위를 벗어나는 신호 — 사용자에게 보고.

- [ ] **Step 3: 재실행 + 커밋**

Run: `uv run pytest -x -q`
Expected: 전체 PASS.

```bash
git add tests/<수정파일>
git commit -m "fix(tests): langchain 1.x API 변경에 맞춰 테스트 보정"
```
수정 없으면 skip.

---

### Task 4: CLI 회귀 — 분석 1회 실행

**Files:**
- Run: `cli/main.py`

- [ ] **Step 1: CLI 실행으로 단일 분석 검증**

CLI는 LLM 키가 필요. 사용자가 평소 쓰는 provider 키가 환경에 있다는 전제. 짧은 분석으로 확인:

Run:
```bash
uv run tradingagents analyze --ticker AAPL --analysts market --debate-rounds 1 --quick-llm gpt-4o-mini --deep-llm gpt-4o-mini
```
(실제 옵션명은 `cli/main.py`의 typer 정의에 맞춰 조정. 위는 예시.)

Expected: 분석이 끝까지 진행되고 최종 decision/confidence가 콘솔에 출력. 중간에 LangChain 관련 TypeError/ImportError가 발생하면 1.x 회귀.

- [ ] **Step 2: 회귀 발견 시 수정**

스택 트레이스가 가리키는 파일을 좁게 수정. 일반적으로:
- `AgentState`/메시지 직렬화 부분
- `ToolNode` 구성

수정 후 재실행해서 같은 분석을 통과시킴.

- [ ] **Step 3: 커밋(수정 시)**

```bash
git add tradingagents/<수정파일>
git commit -m "fix: langchain 1.x에 맞춰 분석 그래프 보정"
```

---

### Task 5: 웹 분석 1회 회귀

**Files:**
- Run: `dev.sh` (백엔드+프론트 동시 실행)

- [ ] **Step 1: dev 서버 기동**

Run(별도 터미널 또는 background): `./dev.sh`
Expected: 백엔드 8000 포트, 프론트 3000 포트가 정상 기동.

- [ ] **Step 2: 분석 실행 + 진행 확인**

브라우저 또는 curl:

```bash
# 로그인(사전 비밀번호 설정되어 있어야 함)
curl -c /tmp/c.txt -X POST http://localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' -H 'X-Requested-With: fetch' \
  -d '{"password":"<your_password>"}'

# 분석 시작
curl -b /tmp/c.txt -X POST http://localhost:8000/api/runs \
  -H 'Content-Type: application/json' -H 'X-Requested-With: fetch' \
  -d '{"ticker":"AAPL","analysis_date":"2026-05-08","analysts":["market"],"debate_rounds":1}'
```
Expected: `{"run_id": "..."}` 응답.

- [ ] **Step 3: 완료까지 대기 + 상태 확인**

```bash
curl -b /tmp/c.txt http://localhost:8000/api/runs/<run_id>
```
주기적으로 호출하여 `status`가 `completed`로 바뀌는지 확인. `failed`면 `error` 필드 확인.

- [ ] **Step 4: dev 서버 종료**

`./dev.sh` 프로세스 종료(Ctrl+C 또는 background면 PID kill).

- [ ] **Step 5: 회귀 없으면 PR 마무리**

이 task는 새 코드를 만들지 않으므로 commit 없음. 아래 "Done" 체크리스트로 마감.

---

## Done

- [ ] `uv run pytest -x -q` 모두 PASS
- [ ] CLI 분석 1회 정상 종료
- [ ] 웹 분석 1회 `completed`까지 진행
- [ ] `pyproject.toml`/`uv.lock` 변경 외에 코드 변경은 deprecation 정리에 한정
- [ ] PR 본문에 "PR-2(분석 후속 대화 기능)의 prerequisite" 명시
