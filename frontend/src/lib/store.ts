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
import { persist } from "zustand/middleware";
import type {
  PipelineEvent,
  PipelineEventType,
  RunStatus,
  StageInfo,
  ClientProfile,
  STAGE_COUNT,
  OrchestrationMode,
} from "./types";

export type UniverseMode = "discovery" | "preset" | "custom";

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
  universeMode: UniverseMode;
  universePreset: string;
  model: string;
  orchestrationMode: OrchestrationMode;
  temperature: number;
  runLabel: string;
  clientProfile: ClientProfile | null;
  market: "us" | "au" | "global" | "mixed";
  benchmarkTicker: string;
  maxPositions: number;
  portfolioVariants: string[];

  // ── Actions ────────────────────────────────────────────────────────
  setRunStarted: (runId: string) => void;
  processEvent: (event: PipelineEvent) => void;
  resetRun: () => void;
  setUniverse: (tickers: string[]) => void;
  setUniverseMode: (mode: UniverseMode) => void;
  setUniversePreset: (preset: string) => void;
  setModel: (model: string) => void;
  setOrchestrationMode: (mode: OrchestrationMode) => void;
  setTemperature: (temp: number) => void;
  setRunLabel: (label: string) => void;
  setClientProfile: (profile: ClientProfile | null) => void;
  setMarket: (market: "us" | "au" | "global" | "mixed") => void;
  setBenchmarkTicker: (ticker: string) => void;
  setMaxPositions: (positions: number) => void;
  togglePortfolioVariant: (variant: string) => void;
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

export const usePipelineStore = create<PipelineStore>()(persist((set, get) => ({
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
  universe: ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "AVGO", "AMD", "ORCL", "CRM",
             "ARM", "TSM", "ANET", "INTC", "MRVL", "QCOM", "NOW", "PLTR", "AI", "SNOW",
             "LLY", "UNH", "JNJ", "ABBV", "MRK", "JPM", "BAC", "GS", "V", "MA",
             "TSLA", "WMT", "COST", "HD", "MCD", "XOM", "CVX", "NEE", "SPY", "QQQ",
             "TLT", "IEF", "LQD", "HYG", "GLD", "IBIT"],
  universeMode: "discovery" as UniverseMode,
  universePreset: "broad_market",
  model: "claude-sonnet-4-6",
  orchestrationMode: "auto",
  temperature: 0.3,
  runLabel: "",
  clientProfile: null,
  market: "us",
  benchmarkTicker: "^GSPC",
  maxPositions: 25,
  portfolioVariants: ["balanced", "higher_return", "lower_volatility"],

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
  setUniverseMode: (universeMode) => set({ universeMode }),
  setUniversePreset: (universePreset) => set({ universePreset }),
  setModel: (model) => set({ model }),
  setOrchestrationMode: (orchestrationMode) => set({ orchestrationMode }),
  setTemperature: (temp) => set({ temperature: temp }),
  setRunLabel: (label) => set({ runLabel: label }),
  setClientProfile: (profile) => set({ clientProfile: profile }),
  setMarket: (market) => set({ market }),
  setBenchmarkTicker: (benchmarkTicker) => set({ benchmarkTicker }),
  setMaxPositions: (maxPositions) => set({ maxPositions }),
  togglePortfolioVariant: (variant) =>
    set((state) => ({
      portfolioVariants: state.portfolioVariants.includes(variant)
        ? state.portfolioVariants.filter((item) => item !== variant)
        : [...state.portfolioVariants, variant],
    })),
  setError: (error) => set({ error }),
}), {
  name: "meridian-run-defaults",
  partialize: (state) => ({
    universe: state.universe,
    universeMode: state.universeMode,
    universePreset: state.universePreset,
    model: state.model,
    orchestrationMode: state.orchestrationMode,
    temperature: state.temperature,
    runLabel: state.runLabel,
    clientProfile: state.clientProfile,
    market: state.market,
    benchmarkTicker: state.benchmarkTicker,
    maxPositions: state.maxPositions,
    portfolioVariants: state.portfolioVariants,
  }),
}));
