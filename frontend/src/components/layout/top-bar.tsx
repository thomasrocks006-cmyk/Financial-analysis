"use client";

import { usePipelineStore } from "@/lib/store";
import { cn, formatDuration } from "@/lib/utils";
import { Activity, Loader2 } from "lucide-react";

export function TopBar() {
  const { activeRunId, runStatus, stages, totalDurationMs } = usePipelineStore();
  const completedCount = stages.filter((s) => s.status === "completed").length;
  const runningStage = stages.find((s) => s.status === "running");

  return (
    <header className="flex h-14 items-center justify-between border-b border-[var(--border)] bg-[var(--surface)] px-6">
      <div className="flex items-center gap-4">
        {activeRunId && (
          <>
            <div className="flex items-center gap-2">
              {runStatus === "running" && (
                <Loader2 className="h-4 w-4 animate-spin text-[var(--accent)]" />
              )}
              <span className="text-sm font-medium text-[var(--text-secondary)]">
                {activeRunId}
              </span>
            </div>
            <div className="h-4 w-px bg-[var(--border)]" />
            <span
              className={cn(
                "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
                runStatus === "running" && "bg-blue-500/10 text-blue-400",
                runStatus === "completed" && "bg-green-500/10 text-green-400",
                runStatus === "failed" && "bg-red-500/10 text-red-400"
              )}
            >
              {runStatus}
            </span>
            <span className="text-xs text-[var(--text-muted)]">
              {completedCount}/15 stages
            </span>
            {runningStage && (
              <span className="text-xs text-[var(--accent)]">
                <Activity className="mr-1 inline h-3 w-3" />
                {runningStage.label}
              </span>
            )}
          </>
        )}
      </div>

      <div className="flex items-center gap-4">
        {totalDurationMs !== null && (
          <span className="text-xs text-[var(--text-muted)]">
            Total: {formatDuration(totalDurationMs)}
          </span>
        )}
      </div>
    </header>
  );
}
