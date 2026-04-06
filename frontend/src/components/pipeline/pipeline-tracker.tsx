"use client";

import { usePipelineStore } from "@/lib/store";
import { cn, formatDuration } from "@/lib/utils";
import { STAGE_COUNT } from "@/lib/types";
import { useState, useEffect } from "react";

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

export function PipelineTracker({
  onStageClick,
}: {
  onStageClick?: (stageNum: number) => void;
}) {
  const stages = usePipelineStore((s) => s.stages);
  const completedCount = stages.filter((s) => s.status === "completed").length;
  const [pulse, setPulse] = useState(true);

  useEffect(() => {
    const t = setInterval(() => setPulse((p) => !p), 800);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="border border-[var(--border)] bg-[var(--surface)]">
      {/* Header row */}
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-[var(--border)] bg-[var(--surface-2)]">
        <span className="text-[var(--text-label)] text-[9px] tracking-[.1em] uppercase">
          Pipeline Stages
        </span>
        <span className="text-[var(--text-muted)] text-[9px] tabular-nums">
          {completedCount}/{STAGE_COUNT}
        </span>
      </div>

      {/* Column headers */}
      <div
        className="grid px-3 py-1 border-b border-[var(--border)]"
        style={{ gridTemplateColumns: "28px 1fr 72px 64px" }}
      >
        <span className="text-[var(--text-muted)] text-[8px] tracking-[.08em]">S#</span>
        <span className="text-[var(--text-muted)] text-[8px] tracking-[.08em]">STAGE</span>
        <span className="text-[var(--text-muted)] text-[8px] tracking-[.08em] text-right">STATUS</span>
        <span className="text-[var(--text-muted)] text-[8px] tracking-[.08em] text-right">DUR</span>
      </div>

      {/* Stage rows */}
      {stages.map((stage) => (
        <button
          key={stage.stage_num}
          onClick={() => onStageClick?.(stage.stage_num)}
          className={cn(
            "grid w-full px-3 py-1.5 border-b border-[var(--border)] text-left hover:bg-[var(--surface-2)] transition-colors",
            stage.status === "running" && "bg-[var(--accent-faint)]"
          )}
          style={{ gridTemplateColumns: "28px 1fr 72px 64px" }}
        >
          <span className="text-[var(--text-muted)] text-[10px] tabular-nums">
            {String(stage.stage_num).padStart(2, "0")}
          </span>
          <span
            className={cn(
              "text-[10px] truncate pr-2",
              stage.status === "running" ? "text-[var(--accent)]" : "text-[var(--text-secondary)]"
            )}
          >
            {stage.label.toUpperCase()}
          </span>
          <span className={cn("text-[10px] text-right tabular-nums", statusColor(stage.status))}>
            {statusSymbol(stage.status, pulse)}{" "}
            {stage.status !== "pending" && stage.status.slice(0, 4).toUpperCase()}
          </span>
          <span className="text-[10px] text-right text-[var(--text-muted)] tabular-nums">
            {stage.duration_ms > 0 ? formatDuration(stage.duration_ms) : "—"}
          </span>
        </button>
      ))}
    </div>
  );
}
