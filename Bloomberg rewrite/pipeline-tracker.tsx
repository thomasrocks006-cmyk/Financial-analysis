"use client";

import { usePipelineStore, type StageState } from "@/lib/store";
import { cn, formatDuration } from "@/lib/utils";
import { STAGE_COUNT } from "@/lib/types";

function statusSymbol(status: string, pulse: boolean): string {
  switch (status) {
    case "completed": return "✓";
    case "running":   return pulse ? "►" : "▷";
    case "failed":    return "✗";
    case "skipped":   return "—";
    default:          return "○";
  }
}

function statusColor(status: string): string {
  switch (status) {
    case "completed": return "text-[var(--success)]";
    case "running":   return "text-[var(--accent)]";
    case "failed":    return "text-[var(--error)]";
    default:          return "text-[var(--text-muted)]";
  }
}

import { useState, useEffect } from "react";

export function PipelineTracker({
  onStageClick,
}: {
  onStageClick?: (stageNum: number) => void;
}) {
  const stages       = usePipelineStore((s) => s.stages);
  const completedCount = stages.filter((s) => s.status === "completed").length;
  const progress       = (completedCount / STAGE_COUNT) * 100;

  const [pulse, setPulse] = useState(true);
  useEffect(() => {
    const t = setInterval(() => setPulse((p) => !p), 800);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="border border-[var(--border)] bg-[var(--surface)] h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--border)] bg-[var(--surface-2)] flex-shrink-0">
        <span className="text-[var(--accent)] text-[10px] tracking-[.1em]">
          PIPELINE STATUS
        </span>
        <span className="text-[var(--text-muted)] text-[10px]">
          {completedCount}/{STAGE_COUNT}
        </span>
      </div>

      {/* Progress bar */}
      <div className="h-px w-full bg-[var(--border-2)] flex-shrink-0">
        <div
          className="h-full bg-[var(--accent)] transition-all duration-500"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Column headers */}
      <div className="grid px-3 py-1 border-b border-[var(--border-2)] flex-shrink-0"
           style={{ gridTemplateColumns: "28px 1fr 72px 64px" }}>
        {["S#", "STAGE", "STATUS", "DUR"].map((h) => (
          <span key={h} className="text-[var(--text-label)] text-[9px] tracking-[.08em]">
            {h}
          </span>
        ))}
      </div>

      {/* Stage rows */}
      <div className="flex-1 overflow-auto">
        {stages.map((stage) => (
          <button
            key={stage.stage_num}
            onClick={() => onStageClick?.(stage.stage_num)}
            className={cn(
              "grid w-full px-3 py-1 text-left border-b border-[var(--border-2)] transition-colors",
              "hover:bg-[var(--surface-2)]",
              stage.status === "running" && "bg-[var(--accent-faint)]"
            )}
            style={{ gridTemplateColumns: "28px 1fr 72px 64px" }}
          >
            <span className="text-[var(--text-muted)] text-[10px]">
              S{String(stage.stage_num).padStart(2, "0")}
            </span>
            <span
              className={cn(
                "text-[11px] truncate",
                stage.status === "running"
                  ? "text-[var(--accent)]"
                  : stage.status === "completed"
                  ? "text-[var(--text-secondary)]"
                  : "text-[var(--text-muted)]"
              )}
            >
              {stage.label.toUpperCase()}
            </span>
            <span
              className={cn("text-[10px] tracking-[.06em]", statusColor(stage.status))}
            >
              <span className={cn(stage.status === "running" && "stage-running")}>
                {statusSymbol(stage.status, pulse)}
              </span>{" "}
              {stage.status === "completed"
                ? "DONE"
                : stage.status === "running"
                ? "RUN"
                : stage.status === "failed"
                ? "FAIL"
                : stage.status === "skipped"
                ? "SKIP"
                : "WAIT"}
            </span>
            <span className="text-[var(--info)] text-[10px] tabular-nums">
              {stage.duration_ms > 0
                ? formatDuration(stage.duration_ms)
                : stage.status === "running"
                ? "..."
                : ""}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
