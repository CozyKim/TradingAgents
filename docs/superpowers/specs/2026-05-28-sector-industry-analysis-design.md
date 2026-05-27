# 산업/섹터 분석 — 설계 스펙

- 작성일: 2026-05-28
- 대상: `tradingagents/graph_sector/*`(신규), `tradingagents_web/{api,services,models,schemas}/sector*`(신규), `web/app/(workspace)/sectors/*`(신규), `web/components/sector/*`(신규)

## 1. 목적

기존 종목(티커) 단위 분석 파이프라인 위에 **산업/섹터 단위 리서치 파이프라인**을 추가한다. 사용자가 AI · 전력 · 반도체(메모리) · 반도체(비메모리) · 로봇 · 우주 같은 산업을 선택하면 (a) 가치사슬을 단계별로 분해하고 (b) 각 단계의 핵심 기업과 점유율을 출처와 함께 정리한 다음 (c) 그 결과에서 도출된 후보 종목을 클릭 한 번으로 기존 종목 분석 파이프라인으로 넘긴다. 산업 → 후보 종목 드릴다운이 핵심 동선이다.

## 2. 현재 상태

- **종목 분석**: `tradingagents/graph/trading_graph.py`가 4종 분석가(Market/Social/News/Fundamentals) → Bull/Bear 토론 → Trader → Risk를 LangGraph로 실행. `tradingagents_web/services/runner.py::RealRunner`가 `astream()`을 돌면서 phase 전이를 EventBus로 SSE에 발행하고, 결과를 `Analysis` row로 저장한다.
- **산업 분석 없음**: 섹터/산업 차원의 컨텍스트는 어디서도 다루지 않는다. fundamentals_analyst는 단일 종목의 재무제표만 본다.
- **데이터 소스**: yfinance, Alpha Vantage, Finnhub, StockTwits. 웹 검색(Tavily 등) 도구는 아직 없다.
- **워크벤치**: Next.js 14 워크스페이스에 `portfolio / run / history / schedules / alerts / settings` 6개 메뉴가 존재. `sectors`는 신규로 추가된다.

## 3. 브레인스토밍에서 확정된 결정

1. **기능 위치**: 산업 리포트 → 후보 종목 발굴 흐름. 산업 리포트가 일등급 자산이고, 그 결과의 일부로 "이 종목 분석" 버튼이 기존 `/run` 파이프라인을 호출한다.
2. **데이터 소스**: LLM 지식 + 웹 검색(Tavily). 사용자 업로드는 비범위.
3. **섹터 관리**: 프리셋 6종(AI · 전력 · 반도체(메모리) · 반도체(비메모리) · 로봇 · 우주)을 마이그레이션 시드로 박고, 사용자는 `+ New sector` 폼으로 자유롭게 추가한다. 프리셋은 삭제 불가, 사용자 정의는 삭제 가능.
4. **분석 구조**: 4단계 LangGraph 그래프 — Macro Overview → Value-Chain Map → Competitive Landscape → Investment Outlook. 종목 분석과 같은 phase 매핑 패턴.
5. **실행/보관**: 수동 실행(`Refresh report` 버튼)만 제공. 결과는 `sector_reports` 테이블에 버전 단위로 누적(불변 히스토리). 자동 cron 트리거는 비범위.
6. **점유율 표현**: 각 기업 항목은 `{value%, basis: reported|estimated|unknown, confidence: high|medium|low, sources: [url]}`로 구조화. UI에 basis 배지와 출처 팝오버를 둔다.
7. **가치사슬 UI**: 보고서 본문은 Markdown, 가치사슬 도식은 LLM이 출력한 Mermaid `graph LR` 구문을 클라이언트에서 dynamic import한 mermaid 라이브러리로 렌더링.
8. **웹 검색 통합 방식**: LangGraph 노드 내부 도구로 통합하되, 노드별·전체 호출 횟수 가드를 두어 ReAct 루프가 비용을 폭주시키는 일을 막는다.

## 4. 데이터 모델

### 4.1 `tradingagents_web/models/sector.py`

```python
class Sector(Base):
    __tablename__ = "sectors"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)  # 검색 시드 + 별명
    is_preset: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    reports: Mapped[list["SectorReport"]] = relationship(back_populates="sector", cascade="all, delete-orphan")
    runs: Mapped[list["SectorRun"]] = relationship(back_populates="sector", cascade="all, delete-orphan")
```

`slug`는 사용자가 입력한 `name`에서 자동 정규화(`반도체(메모리)` → `semiconductor-memory`처럼 한글은 영문 키워드 우선, 충돌 시 `-2` 접미). 프리셋 6종은 고정 slug.

### 4.2 `tradingagents_web/models/sector_run.py`

```python
class SectorRun(Base):
    __tablename__ = "sector_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID
    sector_id: Mapped[int] = mapped_column(ForeignKey("sectors.id"))
    status: Mapped[str] = mapped_column(String(16))  # running | completed | failed
    phase: Mapped[str | None] = mapped_column(String(32), nullable=True)  # macro | value_chain | competitive | outlook
    started_at: Mapped[datetime]
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_quick_model: Mapped[str | None]
    llm_deep_model: Mapped[str | None]
    search_call_count: Mapped[int] = mapped_column(default=0)

    sector: Mapped["Sector"] = relationship(back_populates="runs")
    report: Mapped["SectorReport | None"] = relationship(back_populates="run", uselist=False)
```

### 4.3 `tradingagents_web/models/sector_report.py`

```python
class SectorReport(Base):
    __tablename__ = "sector_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    sector_id: Mapped[int] = mapped_column(ForeignKey("sectors.id"), index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("sector_runs.id"), unique=True)
    version: Mapped[int]  # 섹터 내 자동 증분 (1, 2, 3...)
    report_md: Mapped[str] = mapped_column(Text)
    value_chain_mermaid: Mapped[str] = mapped_column(Text)
    companies: Mapped[list[dict]] = mapped_column(JSON, default=list)
    outlook_summary: Mapped[str] = mapped_column(Text)
    candidate_tickers: Mapped[list[dict]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    sector: Mapped["Sector"] = relationship(back_populates="reports")
    run: Mapped["SectorRun"] = relationship(back_populates="report")

    __table_args__ = (UniqueConstraint("sector_id", "version"),)
```

`companies` JSON 스키마:
```json
[
  {
    "name": "ASML",
    "ticker": "ASML",
    "stage": "Upstream — 노광장비",
    "share_value": 65.0,
    "share_basis": "reported",
    "confidence": "high",
    "sources": ["https://...", "https://..."]
  }
]
```

`candidate_tickers` JSON 스키마:
```json
[
  {"ticker": "005930", "name": "삼성전자", "stage": "Downstream — 메모리", "reason": "..."}
]
```

### 4.4 Alembic 마이그레이션

신규 마이그레이션 1건: 위 3개 테이블 + 6종 프리셋 시드 인라인.

| slug | name | keywords |
|---|---|---|
| `ai` | AI · 인공지능 | `["AI accelerator", "GPU", "foundation models", "NVIDIA", "OpenAI"]` |
| `power` | 전력 · 그리드 | `["power grid", "transformer", "HVDC", "AI data center power"]` |
| `semiconductor-memory` | 반도체 — 메모리 | `["DRAM", "NAND", "HBM", "Samsung", "SK Hynix", "Micron"]` |
| `semiconductor-logic` | 반도체 — 비메모리 | `["foundry", "fabless", "EUV", "TSMC", "ASML", "Applied Materials"]` |
| `robotics` | 로봇 | `["humanoid", "industrial robot", "Boston Dynamics", "Tesla Optimus"]` |
| `space` | 우주 | `["launch vehicle", "satellite", "SpaceX", "Rocket Lab", "Starlink"]` |

## 5. 그래프 (`tradingagents/graph_sector/`)

### 5.1 상태

```python
@dataclass
class SectorState:
    sector_slug: str
    sector_name: str
    keywords: list[str]
    messages: Annotated[Sequence[AnyMessage], add_messages]
    macro_report: str = ""
    value_chain_md: str = ""
    value_chain_mermaid: str = ""
    companies: list[dict] = field(default_factory=list)
    outlook_md: str = ""
    candidate_tickers: list[dict] = field(default_factory=list)
    search_call_count: int = 0  # web_search 도구가 증분
    search_budget: int = 12      # 전체 예산
    node_search_budget: int = 3  # 노드 내부에서 별도 카운터 유지
```

### 5.2 노드 4개

| 노드 | 모델 | 도구 | 출력 강제 |
|---|---|---|---|
| `macro_overview` | deep | `web_search` | Markdown(자유 텍스트) |
| `value_chain` | deep | `web_search` | JSON `{stages: [{name, description}], mermaid: "graph LR ..."}` |
| `competitive_landscape` | deep | `web_search` | JSON `{companies: [{name, ticker?, stage, share_value, share_basis, confidence, sources}]}` |
| `investment_outlook` | deep | (도구 없음) | JSON `{summary_md, candidate_tickers: [{ticker, name, stage, reason}]}` |

각 JSON 강제는 OpenAI `response_format` / Anthropic tools 스펙 양쪽을 지원하는 `langchain_core.utils.json` 파서 + 1회 재시도 + 실패 시 `basis="unknown"` fallback.

`value_chain` 노드의 mermaid 구문은 다음 형태 권장:
```
graph LR
  U1[EUV 노광장비] --> M1[웨이퍼 제조]
  U2[포토레지스트] --> M1
  M1 --> D1[메모리 DRAM]
  M1 --> D2[메모리 NAND]
```

### 5.3 `web_search` 도구

`tradingagents/graph_sector/tools/web_search.py`:

```python
from langchain_core.tools import tool
from tavily import TavilyClient

@tool
def web_search(query: str) -> list[dict]:
    """Search the web for recent industry/market information.

    Returns a list of {title, url, snippet}. Empty list if budget exhausted
    or API key missing.
    """
    state = _current_state()  # 노드가 InjectedState로 주입
    if state.search_call_count >= state.search_budget:
        return []
    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    results = client.search(query, max_results=5, search_depth="advanced")
    state.search_call_count += 1
    return [{"title": r["title"], "url": r["url"], "snippet": r["content"]} for r in results.get("results", [])]
```

전체 예산 초과 시 빈 리스트를 돌려주고 LLM에는 ToolMessage로 `"Search budget exhausted (12/12). Conclude with existing context."`를 함께 주입.

### 5.4 그래프 빌더 (`sector_graph.py`)

```python
def build_sector_graph(quick_llm, deep_llm) -> CompiledStateGraph:
    g = StateGraph(SectorState)
    g.add_node("macro_overview", make_macro_node(deep_llm))
    g.add_node("value_chain", make_value_chain_node(deep_llm))
    g.add_node("competitive_landscape", make_competitive_node(deep_llm))
    g.add_node("investment_outlook", make_outlook_node(deep_llm))
    # ToolNode 1개를 macro/value_chain/competitive에 공유
    g.add_node("tools", ToolNode([web_search]))

    g.set_entry_point("macro_overview")
    g.add_conditional_edges("macro_overview", _route_tools_or("value_chain"))
    g.add_conditional_edges("value_chain", _route_tools_or("competitive_landscape"))
    g.add_conditional_edges("competitive_landscape", _route_tools_or("investment_outlook"))
    g.add_edge("tools", _last_caller)  # 마지막 호출 노드로 복귀
    g.add_edge("investment_outlook", END)
    return g.compile()
```

## 6. Runner & SSE

`tradingagents_web/services/sector_runner.py` — 종목 `runner.py`와 같은 `Runner` Protocol 형태. 차이점:

```python
PHASE_ORDER = ("macro", "value_chain", "competitive", "outlook")
PHASE_LABELS = {
    "macro": "거시 환경",
    "value_chain": "가치사슬",
    "competitive": "경쟁 구도",
    "outlook": "투자 전망",
}
NODE_TO_PHASE = {
    "macro_overview": "macro",
    "value_chain": "value_chain",
    "competitive_landscape": "competitive",
    "investment_outlook": "outlook",
    "tools": None,  # 페이즈 전이 트리거 아님
}
```

페이즈 전이마다 `EventBus`에 `progress` 이벤트(같은 페이로드 형식 — step/total/phase/phase_label). 완료 시 `SectorReport.version = max(prev_version) + 1`로 commit 후 `event: completed {report_id}`.

`WEB_FAKE_RUNNER=true`이면 `FakeSectorRunner`가 0.5s 간격으로 4 페이즈를 흘리고 더미 리포트를 commit — UI/E2E/SSE 흐름을 LLM 호출 없이 검증.

## 7. API

`tradingagents_web/api/sectors.py`:

| Method | Path | 동작 |
|---|---|---|
| GET | `/api/sectors` | 프리셋 + 사용자 정의 전체 |
| POST | `/api/sectors` | 새 섹터 (name, description, keywords) |
| DELETE | `/api/sectors/{id}` | 사용자 정의만, 프리셋은 409 |
| POST | `/api/sectors/{id}/runs` | 새 분석 시작 (llm_quick/deep_model 선택). 동일 섹터에 이미 running이면 409 |
| GET | `/api/sectors/{id}/runs/{rid}/stream` | SSE — 기존 runs와 같은 EventBus |
| GET | `/api/sectors/{id}/reports` | 버전 목록 (id, version, created_at만) |
| GET | `/api/sectors/{id}/reports/{report_id}` | 단일 리포트 전체 |
| GET | `/api/sectors/{id}/reports/latest` | 최신 1건 단축 경로 |

전부 기존 `auth.py` 의존성으로 보호.

## 8. 프론트엔드

### 8.1 라우트

| 경로 | 페이지 |
|---|---|
| `/sectors` | 섹터 카드 그리드(프리셋 6 + 사용자 정의) + `+ New sector` |
| `/sectors/new` | 사용자 정의 섹터 생성 폼 |
| `/sectors/[slug]` | 최신 리포트 + `Refresh report` + 버전 셀렉터 |
| `/sectors/[slug]/runs/[rid]` | 진행 중 분석(SSE phase 진행 UI) |

### 8.2 컴포넌트 (`web/components/sector/`)

- `value-chain-diagram.tsx` — mermaid 클라이언트 dynamic import. SSR 비활성. 다이어그램 노드 클릭 시 해당 stage의 회사 패널로 스크롤(`scrollIntoView`).
- `companies-table.tsx` — stage별 그룹화, share % 정렬, `share_basis` 배지(`reported` = 녹색, `estimated` = 노랑, `unknown` = 회색), 출처 팝오버.
- `candidate-tickers.tsx` — 후보 종목 카드 그리드. 각 카드에 `Run analysis` 버튼 → `/run?ticker=XXX&from_sector=<slug>&from_report=<report_id>`.
- `sector-card.tsx` — 섹터 리스트 카드(name, description, 최신 리포트 created_at).
- `phase-progress.tsx` — 종목 분석의 phase 진행 UI를 재사용(혹은 공통 컴포넌트로 추출).

### 8.3 네비게이션

- `web/components/nav/sidebar.tsx` — Workspace 섹션에 `Sectors` 항목 추가(아이콘 별도).
- `web/components/nav/tab-bar.tsx` — 모바일 하단 탭바에 `Sectors` 추가(또는 More 메뉴로).

### 8.4 `/run` 폼 prefill

`web/app/(workspace)/run/page.tsx`가 `from_sector` / `from_report` 쿼리를 받으면 ticker prefill + 상단 안내 텍스트("산업 리포트 [반도체 — 메모리] v3에서 시작"). 이후 분석 흐름은 그대로.

## 9. 에러 처리 · 가드

| 상황 | 동작 |
|---|---|
| `TAVILY_API_KEY` 미설정 | 부팅 시 logger.warning. `POST /api/sectors/{id}/runs`는 503 + "웹 검색 API 키가 필요합니다" |
| `web_search` 호출 한도 도달 | 도구가 빈 리스트 + ToolMessage 안내. 노드는 그대로 진행 |
| Tavily 4xx/5xx | 노드 단위 logger.warning, 빈 결과, `companies[i].sources=[]` + `confidence="low"` |
| LLM JSON schema 위반 | temp 낮춰 1회 재시도. 재시도 실패 시 best-effort 텍스트 fallback + `basis="unknown"` 강제 |
| 노드 예외 | `SectorRun.status=failed`, `error=traceback short`, SSE `event: error` 발행 후 그래프 종료 |
| 프리셋 섹터 DELETE | 409 Conflict |
| 동일 섹터 동시 분석 | 409 Conflict (`SectorRun.status=running`이 있으면 거부) |
| keywords 미입력 | fallback: `[sector.name + " value chain", sector.name + " market share 2026"]` 자동 생성 |
| 워크트리에서 운영 DB | `dev.sh` 기존 가드 그대로 적용 (`ALLOW_PROD_DB_IN_WORKTREE=1`로만 우회) |

## 10. 테스트 전략

| 레이어 | 도구 | 검증 |
|---|---|---|
| graph_sector 단위 | pytest + LLM 스텁 | 각 노드 JSON 강제 출력 파싱 성공/실패, search budget 가드, mermaid 텍스트 lint |
| sector_runner | pytest + FakeSectorRunner | phase 전이 4개 순서, 실패 시 status=failed 전파, version 자동 증분 |
| API | pytest + httpx AsyncClient | CRUD 인증/권한, 프리셋 보호, 동시 실행 409, SSE handshake |
| 마이그레이션 | pytest | upgrade head 후 6종 프리셋 시드 존재 |
| 프론트 단위 | vitest | companies-table 정렬·필터, candidate-tickers `/run` 링크 생성, mermaid dynamic import 폴백 |
| E2E (Playwright) | `WEB_FAKE_RUNNER=true` 격리 DB | `/sectors` → 분석 실행 → 진행 UI → 리포트 → 후보 종목 → `/run` prefill 확인 |

## 11. 신규 의존성

- **Python**: `tavily-python>=0.5` (혹은 `langchain-tavily`). `mermaid` lint는 클라이언트만 수행하므로 백엔드 의존성 없음.
- **프론트**: `mermaid@^11` — dynamic import로 SSR 비활성. 번들 사이즈는 라이브러리 자체가 무거우니 `/sectors/*` 라우트에서만 lazy-load.
- **환경 변수**: `TAVILY_API_KEY`(필수), `SECTOR_SEARCH_BUDGET`(선택, 기본 12), `SECTOR_NODE_SEARCH_BUDGET`(선택, 기본 3).

## 12. 워크트리

`git worktree add ../.worktrees/feat-sector-analysis -b feat/sector-analysis`로 격리. DEV.md의 워크트리 가드(운영 DB 절대경로 카피 금지)를 따라 워크트리 안에서는 `.env.test` 복사 또는 `WEB_DATABASE_URL=sqlite:///./worktree.db`로 강제. `superpowers:using-git-worktrees` 스킬이 이 단계에 진입.

## 13. 비범위 (이번 마일스톤에서 제외)

- 자동 cron 트리거(스케줄러 통합) — M3 패턴 재사용 가능하지만 별도 마일스톤.
- 산업 비교 뷰(섹터 A vs B) — 종목 history compare와 같은 패턴으로 후속.
- 사용자 업로드 자료 RAG — 별도 인덱스가 필요해 분리.
- 다국어 리포트 — 일단 한국어 단일.
- 알림 트리거 — 산업 리포트가 갱신될 때 in-app/Telegram 발화는 후속.
