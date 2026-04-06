/**
 * API client for the FastAPI backend.
 * All methods return typed results matching the backend schemas.
 */

import type {
  RunRequest,
  RunSummary,
  StageInfo,
  TimingData,
  AuditPacket,
  SavedRun,
  Artifact,
  ProvenancePacket,
  QuantData,
} from "./types";
import { getApiTargetLabel, getRuntimeApiBaseUrl } from "./runtime-settings";

function getApiPrefix(): string {
  return `${getRuntimeApiBaseUrl()}/api/v1`;
}

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers || {}),
      },
    });
  } catch (error) {
    throw new Error(
      `Backend API unreachable at ${getApiTargetLabel()}. Start the FastAPI server on port 8000 or update Settings → Backend URL.`,
    );
  }
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json();
}

// ── Runs ────────────────────────────────────────────────────────────────

export async function startRun(
  request: RunRequest
): Promise<{ run_id: string; status: string; events_url: string }> {
  return fetchJSON(`${getApiPrefix()}/runs`, {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export async function listRuns(): Promise<{
  runs: RunSummary[];
  count: number;
}> {
  return fetchJSON(`${getApiPrefix()}/runs`);
}

export async function getRunStatus(runId: string): Promise<RunSummary> {
  return fetchJSON(`${getApiPrefix()}/runs/${runId}`);
}

export async function getRunResult(
  runId: string
): Promise<Record<string, unknown>> {
  return fetchJSON(`${getApiPrefix()}/runs/${runId}/result`);
}

export async function deleteRun(
  runId: string
): Promise<{ deleted: boolean }> {
  return fetchJSON(`${getApiPrefix()}/runs/${runId}`, { method: "DELETE" });
}

// ── Report ──────────────────────────────────────────────────────────────

export async function getReport(
  runId: string
): Promise<{
  run_id: string;
  report_markdown: string;
  word_count: number;
  estimated_pages: number;
}> {
  return fetchJSON(`${getApiPrefix()}/runs/${runId}/report`);
}

// ── Stages ──────────────────────────────────────────────────────────────

export async function getStages(
  runId: string
): Promise<{ stages: StageInfo[]; count: number }> {
  return fetchJSON(`${getApiPrefix()}/runs/${runId}/stages`);
}

export async function getStageDetail(
  runId: string,
  stageNum: number
): Promise<StageInfo> {
  return fetchJSON(`${getApiPrefix()}/runs/${runId}/stages/${stageNum}`);
}

// ── Audit ───────────────────────────────────────────────────────────────

export async function getAudit(
  runId: string
): Promise<{ audit_packet: AuditPacket }> {
  return fetchJSON(`${getApiPrefix()}/runs/${runId}/audit`);
}

// ── Timings ─────────────────────────────────────────────────────────────

export async function getTimings(
  runId: string
): Promise<{ timings: TimingData }> {
  return fetchJSON(`${getApiPrefix()}/runs/${runId}/timings`);
}

// ── Artifacts ───────────────────────────────────────────────────────────

export async function listArtifacts(
  runId: string
): Promise<{ artifacts: Artifact[]; count: number }> {
  return fetchJSON(`${getApiPrefix()}/runs/${runId}/artifacts`);
}

// ── Provenance ──────────────────────────────────────────────────────────

export async function getProvenance(
  runId: string
): Promise<{ run_id: string; provenance: ProvenancePacket }> {
  return fetchJSON(`${getApiPrefix()}/runs/${runId}/provenance`);
}

// ── Saved runs ──────────────────────────────────────────────────────────

export async function listSavedRuns(): Promise<{
  runs: SavedRun[];
  count: number;
}> {
  return fetchJSON(`${getApiPrefix()}/saved-runs`);
}

export async function loadSavedRun(
  runId: string
): Promise<Record<string, unknown>> {
  return fetchJSON(`${getApiPrefix()}/saved-runs/${runId}`);
}

export async function deleteSavedRun(
  runId: string
): Promise<{ deleted: boolean; run_id: string }> {
  return fetchJSON(`${getApiPrefix()}/saved-runs/${runId}`, { method: "DELETE" });
}

// ── Quant Analytics ─────────────────────────────────────────────────────

export async function getQuant(
  runId: string
): Promise<{ run_id: string; quant: QuantData }> {
  return fetchJSON(`${getApiPrefix()}/runs/${runId}/quant`);
}

// ── PDF Report Download ──────────────────────────────────────────────────

export async function downloadReportPdf(runId: string): Promise<Blob> {
  let res: Response;
  try {
    res = await fetch(`${getApiPrefix()}/runs/${runId}/report/pdf`);
  } catch {
    throw new Error(
      `Backend API unreachable at ${getApiTargetLabel()}. Start the FastAPI server on port 8000 or update Settings → Backend URL.`,
    );
  }
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.blob();
}

// ── Market Data ─────────────────────────────────────────────────────────

export interface MarketQuote {
  sym: string;
  label: string;
  price: number | null;
  change_pct: number | null;
  change_pct_str: string;
  market_cap_bn?: number | null;
  volume?: number | null;
  day_high?: number | null;
  day_low?: number | null;
  "52w_high"?: number | null;
  "52w_low"?: number | null;
  exchange?: string;
  error?: string;
}

export async function getMarketQuotes(tickers: string[]): Promise<{
  quotes: MarketQuote[];
  count: number;
  source: string;
}> {
  if (!tickers.length) return { quotes: [], count: 0, source: "none" };
  const params = new URLSearchParams({ tickers: tickers.join(",") });
  return fetchJSON(`${getApiPrefix()}/market/quotes?${params.toString()}`);
}

export async function getMarketIndices(): Promise<{
  indices: MarketQuote[];
  count: number;
  source: string;
}> {
  return fetchJSON(`${getApiPrefix()}/market/indices`);
}

// ── Universe Presets ─────────────────────────────────────────────────────

export interface UniversePreset {
  id: string;
  label: string;
  description: string;
  asset_classes: string;
  ticker_count: number;
}

export async function getUniversePresets(): Promise<{
  universes: UniversePreset[];
  count: number;
  default: string;
}> {
  return fetchJSON(`${getApiPrefix()}/universes`);
}

export async function getUniverseTickers(name: string): Promise<{
  name: string;
  tickers: string[];
  count: number;
}> {
  return fetchJSON(`${getApiPrefix()}/universes/${encodeURIComponent(name)}`);
}

export function createEventStream(
  runId: string,
  onEvent: (event: { type: string; data: Record<string, unknown> }) => void,
  onError?: (error: Error) => void,
  onClose?: () => void
): () => void {
  const url = `${getRuntimeApiBaseUrl()}/api/v1/runs/${runId}/events`;
  const eventSource = new EventSource(url);

  const eventTypes = [
    "connected",
    "pipeline_started",
    "stage_started",
    "stage_completed",
    "stage_failed",
    "agent_started",
    "agent_completed",
    "llm_call_started",
    "llm_call_completed",
    "artifact_written",
    "pipeline_completed",
    "pipeline_failed",
    "stream_closed",
  ];

  for (const type of eventTypes) {
    eventSource.addEventListener(type, (e) => {
      try {
        const data = JSON.parse((e as MessageEvent).data);
        onEvent({ type, data });
        if (type === "stream_closed" || type === "pipeline_completed" || type === "pipeline_failed") {
          eventSource.close();
          onClose?.();
        }
      } catch (err) {
        onError?.(err instanceof Error ? err : new Error(String(err)));
      }
    });
  }

  eventSource.onerror = () => {
    onError?.(new Error("SSE connection error"));
    eventSource.close();
    onClose?.();
  };

  // Return cleanup function
  return () => {
    eventSource.close();
  };
}

export async function probeBackendConnection(): Promise<{ ok: boolean; target: string }> {
  const target = getApiTargetLabel();
  try {
    await fetchJSON<{ runs: RunSummary[]; count: number }>(`${getApiPrefix()}/runs`);
    return { ok: true, target };
  } catch {
    return { ok: false, target };
  }
}
