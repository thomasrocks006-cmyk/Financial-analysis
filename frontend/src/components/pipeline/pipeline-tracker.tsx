"use client";

import { usePipelineStore, type StageState } from "@/lib/store";
import { cn, formatDuration, stageStatusColor } from "@/lib/utils";
import {
  CheckCircle2,
  Circle,
  Loader2,
  XCircle,
  MinusCircle,
} from "lucide-react";

function StageIcon({ status }: { status: string }) {
  switch (status) {
    case "completed":
      return <CheckCircle2 className="h-4 w-4 text-green-400" />;
    case "running":
      return <Loader2 className="h-4 w-4 animate-spin text-blue-400" />;
    case "failed":
      return <XCircle className="h-4 w-4 text-red-400" />;
    case "skipped":
      return <MinusCircle className="h-4 w-4 text-gray-500" />;
    default:
      return <Circle className="h-4 w-4 text-gray-600" />;
  }
}

function StageRow({
  stage,
  isLast,
  onClick,
}: {
  stage: StageState;
  isLast: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "group relative flex w-full items-center gap-3 rounded-lg p-3 text-left transition-colors",
        "hover:bg-[var(--surface-2)]",
        stage.status === "running" && "bg-blue-500/5 border border-blue-500/20",
        stage.status === "completed" && "opacity-90",
        stage.status === "pending" && "opacity-50"
      )}
    >
      {/* Timeline connector */}
      <div className="flex flex-col items-center">
        <StageIcon status={stage.status} />
        {!isLast && (
          <div
            className={cn(
              "mt-1 w-px flex-1 min-h-[0.75rem]",
              stage.status === "completed" ? "bg-green-400/30" : "bg-[var(--border)]"
            )}
          />
        )}
      </div>

      {/* Content */}
      <div className="flex flex-1 items-center justify-between min-w-0">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-[var(--text-muted)]">
              S{stage.stage_num}
            </span>
            <span
              className={cn(
                "text-sm font-medium truncate",
                stageStatusColor(stage.status)
              )}
            >
              {stage.label}
            </span>
          </div>
          {stage.agent_name && stage.status === "running" && (
            <p className="mt-0.5 text-xs text-[var(--text-muted)] truncate">
              Agent: {stage.agent_name}
            </p>
          )}
        </div>

        {/* Duration */}
        {stage.duration_ms > 0 && (
          <span className="ml-2 text-xs text-[var(--text-muted)] tabular-nums">
            {formatDuration(stage.duration_ms)}
          </span>
        )}
      </div>
    </button>
  );
}

export function PipelineTracker({
  onStageClick,
}: {
  onStageClick?: (stageNum: number) => void;
}) {
  const stages = usePipelineStore((s) => s.stages);
  const completedCount = stages.filter((s) => s.status === "completed").length;
  const progress = (completedCount / 15) * 100;

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-[var(--text-primary)]">
          Pipeline Progress
        </h3>
        <span className="text-xs text-[var(--text-muted)]">
          {completedCount}/15 stages
        </span>
      </div>

      {/* Progress bar */}
      <div className="mb-4 h-1.5 overflow-hidden rounded-full bg-[var(--surface-2)]">
        <div
          className="h-full rounded-full bg-[var(--accent)] transition-all duration-500 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Stage list */}
      <div className="space-y-0.5">
        {stages.map((stage, i) => (
          <StageRow
            key={stage.stage_num}
            stage={stage}
            isLast={i === stages.length - 1}
            onClick={() => onStageClick?.(stage.stage_num)}
          />
        ))}
      </div>
    </div>
  );
}
