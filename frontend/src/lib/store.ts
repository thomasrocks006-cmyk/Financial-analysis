/**
 * Global pipeline state management via Zustand.
 *
 * Tracks:
 *  - Active run ID and status
 *  - Per-stage status/timing (populated from SSE events)
 *  - Live event log (scrollable feed)
 *  - Run configuration (universe, model, client profile)
 */

import { create } from "zustand";
import type {
  PipelineEvent,
  PipelineEventType,
  RunStatus,
  StageInfo,
  ClientProfile,
  STAGE_COUNT,
} from "./types";

export interface StageState {
  stage_num: number;
  label: string;
  status: "pending" | "running" | "completed" | "failed" | "skipped";
  duration_ms: number;
  started_at: string | null;
  agent_name: string | null;
}

export interface LiveEvent {
  id: number;
  type: PipelineEventType;
  stage: number | null;
  label: string | null;
  agent_name: string | null;
  duration_ms: number | null;
  timestamp: string;
  data: Record<string, unknown>;
}

interface PipelineStore {
  // ── Run state ──────────────────────────────────────────────────────
  activeRunId: string | null;
  runStatus: RunStatus | null;
  stages: StageState[];
  events: LiveEvent[];
  eventCounter: number;
  pipelineStartedAt: string | null;
  pipelineCompletedAt: string | null;
  totalDurationMs: number | null;
  error: string | null;

  // ── Config state ───────────────────────────────────────────────────
  universe: string[];
  model: string;
  temperature: number;
  runLabel: string;
  clientProfile: ClientProfile | null;
  market: "us" | "au" | "global" | "mixed";

  // ── Actions ────────────────────────────────────────────────────────
  setRunStarted: (runId: string) => void;
  processEvent: (event: PipelineEvent) => void;
  resetRun: () => void;
  setUniverse: (tickers: string[]) => void;
  setModel: (model: string) => void;
  setTemperature: (temp: number) => void;
  setRunLabel: (label: string) => void;
  setClientProfile: (profile: ClientProfile | null) => void;
  setMarket: (market: "us" | "au" | "global" | "mixed") => void;
  setError: (error: string | null) => void;
}

const STAGE_LABELS: Record<number, string> = {
  0: "Bootstrap",
  1: "Universe Validation",
  2: "Data Ingestion",
  3: "Reconciliation",
  4: "Data QA",
  5: "Evidence Library",
  6: "Sector Analysis",
  7: "Valuation",
  8: "Macro & Geopolitical",
  9: "Risk Assessment",
  10: "Red Team",
  11: "Associate Review",
  12: "Portfolio Construction",
  13: "Report Assembly",
  14: "Monitoring",
};

function createInitialStages(): StageState[] {
  return Array.from({ length: 15 }, (_, i) => ({
    stage_num: i,
    label: STAGE_LABELS[i] || `Stage ${i}`,
    status: "pending" as const,
    duration_ms: 0,
    started_at: null,
    agent_name: null,
  }));
}

export const usePipelineStore = create<PipelineStore>((set, get) => ({
  // Initial state
  activeRunId: null,
  runStatus: null,
  stages: createInitialStages(),
  events: [],
  eventCounter: 0,
  pipelineStartedAt: null,
  pipelineCompletedAt: null,
  totalDurationMs: null,
  error: null,

  // Config defaults
  universe: ["NVDA", "AMD", "AVGO", "MRVL", "ARM", "TSM", "MSFT", "AMZN", "GOOGL", "META", "EQIX", "DLR", "VRT", "DELL", "SMCI"],
  model: "claude-sonnet-4-6",
  temperature: 0.3,
  runLabel: "",
  clientProfile: null,
  market: "us",

  // ── Actions ────────────────────────────────────────────────────────
  setRunStarted: (runId: string) =>
    set({
      activeRunId: runId,
      runStatus: "running",
      stages: createInitialStages(),
      events: [],
      eventCounter: 0,
      pipelineStartedAt: null,
      pipelineCompletedAt: null,
      totalDurationMs: null,
      error: null,
    }),

  processEvent: (event: PipelineEvent) => {
    const state = get();
    const counter = state.eventCounter + 1;

    const liveEvent: LiveEvent = {
      id: counter,
      type: event.event_type,
      stage: event.stage,
      label: event.stage_label,
      agent_name: event.agent_name,
      duration_ms: event.duration_ms,
      timestamp: event.timestamp,
      data: event.data,
    };

    const updates: Partial<PipelineStore> = {
      events: [...state.events, liveEvent].slice(-200), // Keep last 200
      eventCounter: counter,
    };

    switch (event.event_type) {
      case "pipeline_started":
        updates.pipelineStartedAt = event.timestamp;
        updates.runStatus = "running";
        break;

      case "stage_started": {
        const newStages = [...state.stages];
        if (event.stage !== null && newStages[event.stage]) {
          newStages[event.stage] = {
            ...newStages[event.stage],
            status: "running",
            started_at: event.timestamp,
            agent_name: event.agent_name,
          };
        }
        updates.stages = newStages;
        break;
      }

      case "stage_completed": {
        const newStages = [...state.stages];
        if (event.stage !== null && newStages[event.stage]) {
          newStages[event.stage] = {
            ...newStages[event.stage],
            status: "completed",
            duration_ms: event.duration_ms || 0,
          };
        }
        updates.stages = newStages;
        break;
      }

      case "stage_failed": {
        const newStages = [...state.stages];
        if (event.stage !== null && newStages[event.stage]) {
          newStages[event.stage] = {
            ...newStages[event.stage],
            status: "failed",
            duration_ms: event.duration_ms || 0,
          };
        }
        updates.stages = newStages;
        break;
      }

      case "agent_started":
      case "agent_completed":
        // Update agent name on current running stage
        if (event.stage !== null) {
          const newStages = [...state.stages];
          if (newStages[event.stage]) {
            newStages[event.stage] = {
              ...newStages[event.stage],
              agent_name: event.agent_name,
            };
          }
          updates.stages = newStages;
        }
        break;

      case "pipeline_completed":
        updates.runStatus = "completed";
        updates.pipelineCompletedAt = event.timestamp;
        if (event.duration_ms) updates.totalDurationMs = event.duration_ms;
        break;

      case "pipeline_failed":
        updates.runStatus = "failed";
        updates.pipelineCompletedAt = event.timestamp;
        updates.error = (event.data?.reason as string) || "Pipeline failed";
        break;
    }

    set(updates);
  },

  resetRun: () =>
    set({
      activeRunId: null,
      runStatus: null,
      stages: createInitialStages(),
      events: [],
      eventCounter: 0,
      pipelineStartedAt: null,
      pipelineCompletedAt: null,
      totalDurationMs: null,
      error: null,
    }),

  setUniverse: (tickers) => set({ universe: tickers }),
  setModel: (model) => set({ model }),
  setTemperature: (temp) => set({ temperature: temp }),
  setRunLabel: (label) => set({ runLabel: label }),
  setClientProfile: (profile) => set({ clientProfile: profile }),
  setMarket: (market) => set({ market }),
  setError: (error) => set({ error }),
}));
