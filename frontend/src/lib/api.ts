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
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
const API_PREFIX = `${API_BASE}/api/v1`;

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
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
  return fetchJSON(`${API_PREFIX}/runs`, {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export async function listRuns(): Promise<{
  runs: RunSummary[];
  count: number;
}> {
  return fetchJSON(`${API_PREFIX}/runs`);
}

export async function getRunStatus(runId: string): Promise<RunSummary> {
  return fetchJSON(`${API_PREFIX}/runs/${runId}`);
}

export async function getRunResult(
  runId: string
): Promise<Record<string, unknown>> {
  return fetchJSON(`${API_PREFIX}/runs/${runId}/result`);
}

export async function deleteRun(
  runId: string
): Promise<{ deleted: boolean }> {
  return fetchJSON(`${API_PREFIX}/runs/${runId}`, { method: "DELETE" });
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
  return fetchJSON(`${API_PREFIX}/runs/${runId}/report`);
}

// ── Stages ──────────────────────────────────────────────────────────────

export async function getStages(
  runId: string
): Promise<{ stages: StageInfo[]; count: number }> {
  return fetchJSON(`${API_PREFIX}/runs/${runId}/stages`);
}

export async function getStageDetail(
  runId: string,
  stageNum: number
): Promise<StageInfo> {
  return fetchJSON(`${API_PREFIX}/runs/${runId}/stages/${stageNum}`);
}

// ── Audit ───────────────────────────────────────────────────────────────

export async function getAudit(
  runId: string
): Promise<{ audit_packet: AuditPacket }> {
  return fetchJSON(`${API_PREFIX}/runs/${runId}/audit`);
}

// ── Timings ─────────────────────────────────────────────────────────────

export async function getTimings(
  runId: string
): Promise<{ timings: TimingData }> {
  return fetchJSON(`${API_PREFIX}/runs/${runId}/timings`);
}

// ── Artifacts ───────────────────────────────────────────────────────────

export async function listArtifacts(
  runId: string
): Promise<{ artifacts: Artifact[]; count: number }> {
  return fetchJSON(`${API_PREFIX}/runs/${runId}/artifacts`);
}

// ── Provenance ──────────────────────────────────────────────────────────

export async function getProvenance(
  runId: string
): Promise<{ run_id: string; provenance: ProvenancePacket }> {
  return fetchJSON(`${API_PREFIX}/runs/${runId}/provenance`);
}

// ── Saved runs ──────────────────────────────────────────────────────────

export async function listSavedRuns(): Promise<{
  runs: SavedRun[];
  count: number;
}> {
  return fetchJSON(`${API_PREFIX}/saved-runs`);
}

export async function loadSavedRun(
  runId: string
): Promise<Record<string, unknown>> {
  return fetchJSON(`${API_PREFIX}/saved-runs/${runId}`);
}

// ── SSE event stream ────────────────────────────────────────────────────

export function createEventStream(
  runId: string,
  onEvent: (event: { type: string; data: Record<string, unknown> }) => void,
  onError?: (error: Error) => void,
  onClose?: () => void
): () => void {
  const url = `${API_BASE}/api/v1/runs/${runId}/events`;
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
