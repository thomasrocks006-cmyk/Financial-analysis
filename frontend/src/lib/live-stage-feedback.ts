import type { PipelineEventType } from "@/lib/types";

export type StreamState = "connecting" | "connected" | "polling" | "error" | "closed";

type StageNarrative = {
  title: string;
  summary: string;
  successSignal: string;
  stallHint: string;
};

const STAGE_NARRATIVES: Record<number, StageNarrative> = {
  0: {
    title: "Bootstrap the run",
    summary: "Loading config, environment, prompts, and provider readiness before any market work begins.",
    successSignal: "The run clears configuration checks and starts the universe gate.",
    stallHint: "If this stalls, check backend health, API keys, and environment loading.",
  },
  1: {
    title: "Validate the universe",
    summary: "Checking ticker inputs, resolving symbols, and making sure the basket is analyzable.",
    successSignal: "Validated names flow into ingestion with a clean shortlist.",
    stallHint: "If this fails, review invalid symbols, duplicates, or an overly concentrated custom basket.",
  },
  2: {
    title: "Ingest live market data",
    summary: "Pulling fundamentals, price snapshots, targets, and supporting market context from external APIs.",
    successSignal: "Live data packets are persisted for each ticker.",
    stallHint: "If this stalls, suspect provider latency, quota pressure, or an offline backend data plane.",
  },
  3: {
    title: "Reconcile source conflicts",
    summary: "Cross-checking ingestion outputs to flag disagreements and normalize the working dataset.",
    successSignal: "The pipeline records a reconciled view for downstream research.",
    stallHint: "If this fails, inspect upstream ingestion quality and source disagreement tolerances.",
  },
  4: {
    title: "Run data QA",
    summary: "Scoring completeness, checking freshness, and catching malformed fields before evidence work starts.",
    successSignal: "Data quality clears the pipeline into evidence construction.",
    stallHint: "If this blocks, review missing fields, stale payloads, or malformed stage 2/3 outputs.",
  },
  5: {
    title: "Build the evidence ledger",
    summary: "Normalizing claims, sources, provenance, and evidence classes into the canonical research ledger.",
    successSignal: "A claim ledger with valid sources and statuses is persisted.",
    stallHint: "If this blocks, inspect provider quota, malformed claim JSON, or claim/source schema mismatches.",
  },
  6: {
    title: "Assemble sector views",
    summary: "Running sector analysts and fallback cards to frame industry structure, risks, and thesis context.",
    successSignal: "Each routed ticker receives sector coverage for downstream valuation and review.",
    stallHint: "If this degrades, check agent structured output and ticker routing coverage.",
  },
  7: {
    title: "Generate valuation cards",
    summary: "Producing scenario-based valuation outputs, consensus anchors, and entry-quality judgments.",
    successSignal: "A valuation pack is saved for each covered name.",
    stallHint: "If this stalls, inspect malformed agent output or fallback valuation synthesis.",
  },
  8: {
    title: "Set macro and policy context",
    summary: "Combining economy services, regime analysis, and political overlays for downstream portfolio decisions.",
    successSignal: "The run records a usable macro regime memo and policy context.",
    stallHint: "If this blocks, inspect macro service availability or structured-output failures from the macro agent.",
  },
  9: {
    title: "Compute risk overlays",
    summary: "Running stress, factor, overlap, and portfolio risk diagnostics against the active basket.",
    successSignal: "Risk scenarios and overlays are saved for red-team and PM stages.",
    stallHint: "If this stalls, inspect return availability, scenario generation, or quant service outputs.",
  },
  10: {
    title: "Challenge the thesis",
    summary: "Running red-team falsification tests to pressure-test core assumptions before publication.",
    successSignal: "Each covered name carries explicit tests and challenge posture.",
    stallHint: "If this fails, inspect missing falsification coverage or upstream evidence gaps.",
  },
  11: {
    title: "Review publication readiness",
    summary: "Checking audit posture, unresolved issues, and whether the research can proceed to portfolio construction.",
    successSignal: "The run records a clear PASS or FAIL review decision.",
    stallHint: "If this blocks, inspect unresolved fail claims, missing methodology tags, or red-team coverage gaps.",
  },
  12: {
    title: "Construct the portfolio",
    summary: "Sizing positions, checking mandate compliance, applying ESG filters, and taking the IC vote.",
    successSignal: "Committee and mandate checks pass with a publishable portfolio package.",
    stallHint: "If this blocks, inspect concentration, mandate violations, ESG exclusions, or IC rejection reasons.",
  },
  13: {
    title: "Assemble the report",
    summary: "Compiling executive summary, stock cards, appendices, and investor-facing report sections.",
    successSignal: "A markdown report artifact is generated and linked to the run.",
    stallHint: "If this stalls, inspect report assembly inputs and downstream artifact writes.",
  },
  14: {
    title: "Finalize monitoring outputs",
    summary: "Recording the final monitoring, audit, and attribution payloads that close the run.",
    successSignal: "The final monitoring artifact marks the run as complete.",
    stallHint: "If this looks wrong, compare the run summary with the stage 14 artifact and final report path.",
  },
};

export function getStageNarrative(stageNum: number | null | undefined): StageNarrative {
  if (stageNum == null) {
    return {
      title: "Awaiting stage signal",
      summary: "The run is waiting for a concrete stage update from the backend event stream or polling snapshot.",
      successSignal: "The next live event should identify the active stage.",
      stallHint: "If nothing moves, check the SSE connection, backend health, and run status endpoint.",
    };
  }
  return STAGE_NARRATIVES[stageNum] || {
    title: `Stage ${stageNum}`,
    summary: "The pipeline is processing this stage.",
    successSignal: "The next signal should show a completion or blocker update.",
    stallHint: "Inspect the stage detail view and recent events if progress looks stale.",
  };
}

export function getStreamStateMeta(streamState: StreamState): {
  label: string;
  tone: string;
  detail: string;
} {
  switch (streamState) {
    case "connected":
      return {
        label: "LIVE",
        tone: "border-[var(--success)] text-[var(--success)] bg-[var(--success-faint)]",
        detail: "Server-sent events are flowing in real time.",
      };
    case "polling":
      return {
        label: "POLLING",
        tone: "border-[var(--warning)] text-[var(--warning)] bg-[var(--warning-faint)]",
        detail: "The live stream dropped; the page is following the run via snapshots.",
      };
    case "error":
      return {
        label: "ISSUE",
        tone: "border-[var(--error)] text-[var(--error)] bg-[var(--error-faint)]",
        detail: "The page could not maintain a live connection to the backend stream.",
      };
    case "closed":
      return {
        label: "CLOSED",
        tone: "border-[var(--border)] text-[var(--text-muted)] bg-[var(--surface-2)]",
        detail: "The live stream closed after the run reached a terminal state.",
      };
    default:
      return {
        label: "CONNECTING",
        tone: "border-[var(--accent)] text-[var(--accent)] bg-[var(--accent-faint)]",
        detail: "Opening the server-sent event stream for live follow mode.",
      };
  }
}

export function getFailureGuidance(
  stageNum: number | null | undefined,
  blockerSummary?: string | null,
  rawError?: string | null
): string[] {
  const hints: string[] = [];

  if (blockerSummary) {
    hints.push(blockerSummary);
  }
  if (rawError && rawError !== blockerSummary) {
    hints.push(rawError);
  }

  if (stageNum === 0) {
    hints.push("Check /health/details for missing credentials, disabled providers, or an unloaded .env file.");
  } else if (stageNum === 5) {
    hints.push("Inspect the evidence ledger stage output for malformed claim JSON, missing sources, or provider quota exhaustion.");
  } else if (stageNum === 12) {
    hints.push("Review mandate concentration, minimum-position rules, ESG exclusions, and the IC vote breakdown.");
  } else if (stageNum === 14) {
    hints.push("Compare the API summary with the stage 14 artifact if completion status looks inconsistent.");
  }

  if (!hints.length) {
    hints.push("Open the Stage Detail tab and the latest live events to inspect the exact blocker context.");
  }

  return Array.from(new Set(hints));
}

export function triggerEventHaptic(eventType: PipelineEventType): void {
  if (typeof window === "undefined" || !("vibrate" in navigator)) {
    return;
  }

  const pattern =
    eventType === "stage_failed" || eventType === "pipeline_failed"
      ? [120, 60, 120]
      : eventType === "stage_completed" || eventType === "pipeline_completed"
      ? [40, 30, 40]
      : eventType === "stage_started"
      ? [25]
      : null;

  if (pattern) {
    navigator.vibrate(pattern);
  }
}