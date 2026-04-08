"use client";

import { useEffect, useRef } from "react";
import { usePipelineStore, type LiveEvent } from "@/lib/store";
import { getStreamStateMeta, type StreamState } from "@/lib/live-stage-feedback";
import { cn, formatDuration } from "@/lib/utils";
import {
  Activity,
  ArrowRight,
  CheckCircle2,
  AlertTriangle,
  Zap,
  FileText,
} from "lucide-react";

function EventIcon({ type }: { type: string }) {
  switch (type) {
    case "stage_started":
      return <ArrowRight className="h-3 w-3 text-blue-400" />;
    case "stage_completed":
      return <CheckCircle2 className="h-3 w-3 text-green-400" />;
    case "stage_failed":
      return <AlertTriangle className="h-3 w-3 text-red-400" />;
    case "agent_started":
    case "agent_completed":
      return <Activity className="h-3 w-3 text-purple-400" />;
    case "llm_call_started":
    case "llm_call_completed":
      return <Zap className="h-3 w-3 text-yellow-400" />;
    case "artifact_written":
      return <FileText className="h-3 w-3 text-cyan-400" />;
    case "pipeline_started":
    case "pipeline_completed":
      return <CheckCircle2 className="h-3 w-3 text-green-400" />;
    case "pipeline_failed":
      return <AlertTriangle className="h-3 w-3 text-red-400" />;
    default:
      return <Activity className="h-3 w-3 text-gray-400" />;
  }
}

function formatEventTime(iso: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

function eventDescription(event: LiveEvent): string {
  const label = event.label || `Stage ${event.stage}`;
  switch (event.type) {
    case "pipeline_started":
      return `Pipeline started — ${(event.data?.ticker_count as number) || 0} tickers`;
    case "stage_started":
      return `${label} started`;
    case "stage_completed":
      return `${label} completed${event.duration_ms ? ` (${formatDuration(event.duration_ms)})` : ""}`;
    case "stage_failed":
      return `${label} failed${event.data?.reason ? `: ${event.data.reason}` : ""}`;
    case "agent_started":
      return `Agent ${event.agent_name || "unknown"} started`;
    case "agent_completed":
      return `Agent ${event.agent_name || "unknown"} completed${event.duration_ms ? ` (${formatDuration(event.duration_ms)})` : ""}`;
    case "llm_call_started":
      return `LLM call dispatched${event.data?.model ? ` → ${event.data.model}` : ""}`;
    case "llm_call_completed":
      return `LLM response received${event.duration_ms ? ` (${formatDuration(event.duration_ms)})` : ""}`;
    case "artifact_written":
      return `Artifact saved: ${(event.data?.filename as string) || "file"}`;
    case "pipeline_completed":
      return `Pipeline completed successfully${event.duration_ms ? ` — total ${formatDuration(event.duration_ms)}` : ""}`;
    case "pipeline_failed":
      return `Pipeline failed${event.data?.blocked_at !== undefined ? ` at stage ${event.data.blocked_at}` : ""}`;
    default:
      return event.type;
  }
}

function EventRow({ event }: { event: LiveEvent }) {
  return (
    <div className="flex items-start gap-2 py-1.5 px-2 hover:bg-[var(--surface-2)] rounded text-xs transition-colors">
      <span className="mt-0.5 flex-shrink-0">
        <EventIcon type={event.type} />
      </span>
      <span className="text-[var(--text-muted)] tabular-nums flex-shrink-0 w-16">
        {formatEventTime(event.timestamp)}
      </span>
      <span
        className={cn(
          "flex-1",
          event.type.includes("failed") ? "text-red-400" : "text-[var(--text-secondary)]"
        )}
      >
        {eventDescription(event)}
      </span>
    </div>
  );
}

export function LiveEventFeed({
  streamState = "connecting",
  statusMessage,
}: {
  streamState?: StreamState;
  statusMessage?: string;
}) {
  const events = usePipelineStore((s) => s.events);
  const bottomRef = useRef<HTMLDivElement>(null);
  const streamMeta = getStreamStateMeta(streamState);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events.length]);

  return (
    <div className="border border-[var(--border)] bg-[var(--surface)] flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[var(--border)] bg-[var(--surface-2)] px-4 py-2">
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-[var(--accent)]" />
          <h3 className="text-[10px] tracking-[.1em] text-[var(--text-label)] uppercase">
            Live Event Feed
          </h3>
        </div>
        <div className="flex items-center gap-2">
          <span className={cn("rounded-full border px-2 py-0.5 text-[9px] tracking-[.08em] uppercase", streamMeta.tone)}>
            {streamMeta.label}
          </span>
          <span className="text-[10px] text-[var(--text-muted)] tabular-nums">
            {events.length} events
          </span>
        </div>
      </div>

      <div className="border-b border-[var(--border)] px-4 py-2 text-[11px] text-[var(--text-secondary)]">
        {statusMessage || streamMeta.detail}
      </div>

      {/* Event list */}
      <div className="flex-1 overflow-auto max-h-[500px] p-1">
        {events.length === 0 ? (
          <div className="flex items-center justify-center p-8 text-[11px] text-[var(--text-muted)]">
            Waiting for pipeline events…
          </div>
        ) : (
          <>
            {events.map((event) => (
              <EventRow key={event.id} event={event} />
            ))}
            <div ref={bottomRef} />
          </>
        )}
      </div>
    </div>
  );
}
