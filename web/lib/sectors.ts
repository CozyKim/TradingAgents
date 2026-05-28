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
  return all.find((s) => s.slug === slug) ?? null;
}
