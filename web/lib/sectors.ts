export type ShareBasis = "reported" | "estimated" | "unknown";
export type Confidence = "high" | "medium" | "low";

export interface SectorSummary {
  id: number;
  slug: string;
  name: string;
  description: string | null;
  keywords: string[];
  is_preset: boolean;
  created_at: string;
  latest_report_version: number | null;
  latest_report_at: string | null;
}

export interface CompanyShare {
  name: string;
  ticker: string | null;
  stage: string;
  share_value: number;
  share_basis: ShareBasis;
  confidence: Confidence;
  sources: string[];
}

export interface CandidateTicker {
  ticker: string;
  name: string;
  stage: string;
  reason: string;
}

export interface SectorReport {
  id: number;
  sector_id: number;
  run_id: string;
  version: number;
  report_md: string;
  value_chain_mermaid: string;
  companies: CompanyShare[];
  outlook_summary: string;
  candidate_tickers: CandidateTicker[];
  created_at: string;
}

export interface SectorReportSummary {
  id: number;
  version: number;
  created_at: string;
}

export interface SectorRun {
  id: string;
  sector_id: number;
  status: "running" | "completed" | "failed";
  phase: string | null;
  started_at: string;
  finished_at: string | null;
  error: string | null;
  search_call_count: number;
}

// All mutating fetchers send the CSRF marker every other workspace fetch uses.
const XHR_HEADERS = { "X-Requested-With": "fetch" };

export async function listSectors(): Promise<SectorSummary[]> {
  const r = await fetch("/api/sectors", { credentials: "include" });
  if (!r.ok) throw new Error(`listSectors ${r.status}`);
  return r.json();
}

export async function createSector(input: {
  name: string;
  description?: string;
  keywords?: string[];
}): Promise<SectorSummary> {
  const r = await fetch("/api/sectors", {
    method: "POST",
    headers: { "content-type": "application/json", ...XHR_HEADERS },
    credentials: "include",
    body: JSON.stringify(input),
  });
  if (!r.ok) {
    const detail = await r.text();
    throw new Error(`createSector ${r.status}: ${detail}`);
  }
  return r.json();
}

export async function deleteSector(id: number): Promise<void> {
  const r = await fetch(`/api/sectors/${id}`, {
    method: "DELETE",
    headers: XHR_HEADERS,
    credentials: "include",
  });
  if (!r.ok) throw new Error(`deleteSector ${r.status}`);
}

export async function startSectorRun(
  sectorId: number,
  payload: { llm_quick_model?: string; llm_deep_model?: string } = {},
): Promise<SectorRun> {
  const r = await fetch(`/api/sectors/${sectorId}/runs`, {
    method: "POST",
    headers: { "content-type": "application/json", ...XHR_HEADERS },
    credentials: "include",
    body: JSON.stringify(payload),
  });
  if (!r.ok) {
    const detail = await r.text();
    throw new Error(`startSectorRun ${r.status}: ${detail}`);
  }
  return r.json();
}

export async function getLatestReport(sectorId: number): Promise<SectorReport | null> {
  const r = await fetch(`/api/sectors/${sectorId}/reports/latest`, {
    credentials: "include",
  });
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`getLatestReport ${r.status}`);
  return r.json();
}

export async function listReports(sectorId: number): Promise<SectorReportSummary[]> {
  const r = await fetch(`/api/sectors/${sectorId}/reports`, {
    credentials: "include",
  });
  if (!r.ok) throw new Error(`listReports ${r.status}`);
  return r.json();
}

export async function getReport(sectorId: number, reportId: number): Promise<SectorReport> {
  const r = await fetch(`/api/sectors/${sectorId}/reports/${reportId}`, {
    credentials: "include",
  });
  if (!r.ok) throw new Error(`getReport ${r.status}`);
  return r.json();
}

export async function getSectorBySlug(slug: string): Promise<SectorSummary | null> {
  const all = await listSectors();
  // useParams()가 경로 세그먼트를 percent-encoded 상태로 넘길 수 있어,
  // 한글 등 비-ASCII slug는 DB의 디코딩된 값과 직접 비교하면 어긋난다.
  // 원본과 디코딩본을 모두 비교해 양쪽 케이스를 안전하게 매칭한다.
  let decoded = slug;
  try {
    decoded = decodeURIComponent(slug);
  } catch {
    /* 잘못된 인코딩이면 원본 그대로 비교 */
  }
  return all.find((s) => s.slug === slug || s.slug === decoded) ?? null;
}

export async function getActiveRun(sectorId: number): Promise<SectorRun | null> {
  // Backend returns null (literal JSON `null`) when no running run exists.
  const r = await fetch(`/api/sectors/${sectorId}/runs/active`, {
    credentials: "include",
  });
  if (!r.ok) throw new Error(`getActiveRun ${r.status}`);
  return r.json();
}

export interface TrendingSignals {
  web_trend: number;
  community_volume: number;
  sentiment: number;
  momentum: number;
}

export interface TrendingSector {
  name: string;
  description: string;
  keywords: string[];
  tickers: string[];
  hotness_score: number;
  signals: TrendingSignals;
  rationale: string;
}

export async function startTrendingScan(): Promise<{ job_id: string }> {
  const r = await fetch("/api/sectors/trending", {
    method: "POST",
    headers: { "content-type": "application/json", ...XHR_HEADERS },
    credentials: "include",
  });
  if (!r.ok) {
    const detail = await r.text();
    throw new Error(`startTrendingScan ${r.status}: ${detail}`);
  }
  return r.json();
}

export async function cancelSectorRun(
  sectorId: number,
  runId: string,
): Promise<void> {
  const r = await fetch(
    `/api/sectors/${sectorId}/runs/${encodeURIComponent(runId)}`,
    { method: "DELETE", headers: XHR_HEADERS, credentials: "include" },
  );
  if (!r.ok) throw new Error(`cancelSectorRun ${r.status}`);
}

export async function cancelTrendingScan(jobId: string): Promise<void> {
  const r = await fetch(
    `/api/sectors/trending/${encodeURIComponent(jobId)}`,
    { method: "DELETE", headers: XHR_HEADERS, credentials: "include" },
  );
  if (!r.ok) throw new Error(`cancelTrendingScan ${r.status}`);
}

export interface TrendingScanSummary {
  id: number;
  created_at: string;
  sector_count: number;
}

export interface TrendingScanDetail {
  id: number;
  created_at: string;
  sectors: TrendingSector[];
}

export async function listTrendingScans(): Promise<TrendingScanSummary[]> {
  const r = await fetch("/api/sectors/trending/scans", { credentials: "include" });
  if (!r.ok) throw new Error(`listTrendingScans ${r.status}`);
  return r.json();
}

export async function getTrendingScan(id: number): Promise<TrendingScanDetail> {
  const r = await fetch(`/api/sectors/trending/scans/${id}`, {
    credentials: "include",
  });
  if (!r.ok) throw new Error(`getTrendingScan ${r.status}`);
  return r.json();
}

export type TrendingStreamHandlers = {
  onProgress?: (data: { stage?: string; message?: string; progress?: string }) => void;
  onHeartbeat?: () => void;
  onDone?: (sectors: TrendingSector[], scanId?: number) => void;
  onError?: (message: string) => void;
  onCancelled?: () => void;
};

/** Subscribe to a trending scan's SSE stream. Returns a cancel function. */
export function openTrendingStream(
  jobId: string,
  handlers: TrendingStreamHandlers,
): () => void {
  const es = new EventSource(
    `/api/sectors/trending/${encodeURIComponent(jobId)}/stream`,
    { withCredentials: true },
  );
  // Track whether the stream ended normally via the "close" event.
  let closed = false;

  es.addEventListener("progress", (raw) => {
    try {
      handlers.onProgress?.(JSON.parse((raw as MessageEvent).data));
    } catch {
      /* ignore */
    }
  });
  es.addEventListener("heartbeat", () => handlers.onHeartbeat?.());
  es.addEventListener("cancelled", () => {
    closed = true;
    handlers.onCancelled?.();
    es.close();
  });
  es.addEventListener("done", (raw) => {
    try {
      const data = JSON.parse((raw as MessageEvent).data);
      handlers.onDone?.(data.sectors ?? [], data.scan_id);
    } catch {
      handlers.onDone?.([]);
    }
  });
  es.addEventListener("error", (raw) => {
    try {
      handlers.onError?.(JSON.parse((raw as MessageEvent).data).message ?? "오류");
    } catch {
      /* EventSource connection error event has no JSON body */
    }
  });
  es.addEventListener("close", () => {
    closed = true;
    es.close();
  });
  // Guard against network drops that don't emit a server-side "error" event.
  // Only fire once the EventSource is fully CLOSED and not via a normal close.
  es.onerror = () => {
    if (!closed && es.readyState === EventSource.CLOSED) {
      handlers.onError?.("스트림 연결이 끊겼습니다.");
    }
  };
  return () => {
    closed = true;
    es.close();
  };
}

export type SectorRunStreamHandlers = {
  onProgress?: (phase: string | null) => void;
  onHeartbeat?: () => void;
  onDone?: () => void;
  onError?: (message: string) => void;
  onCancelled?: () => void;
};

/** Subscribe to a sector run's SSE stream. Returns a cancel function. */
export function openSectorRunStream(
  sectorId: number,
  runId: string,
  handlers: SectorRunStreamHandlers,
): () => void {
  const es = new EventSource(
    `/api/sectors/${sectorId}/runs/${encodeURIComponent(runId)}/stream`,
    { withCredentials: true },
  );
  es.addEventListener("progress", (raw) => {
    try {
      const d = JSON.parse((raw as MessageEvent).data);
      handlers.onProgress?.(typeof d.phase === "string" ? d.phase : null);
    } catch {
      /* ignore malformed payload */
    }
  });
  es.addEventListener("heartbeat", () => handlers.onHeartbeat?.());
  es.addEventListener("done", () => handlers.onDone?.());
  es.addEventListener("cancelled", () => handlers.onCancelled?.());
  es.addEventListener("error", (raw) => {
    // Server-sent `event: error` carries a JSON body; native connection-error
    // events do not — those are left to the client-side stall timer.
    try {
      handlers.onError?.(JSON.parse((raw as MessageEvent).data).message ?? "오류");
    } catch {
      /* connection blip — ignore */
    }
  });
  es.addEventListener("close", () => es.close());
  return () => es.close();
}
