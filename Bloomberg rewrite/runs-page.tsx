"use client";

import { useQuery } from "@tanstack/react-query";
import { listRuns, deleteRun } from "@/lib/api";
import Link from "next/link";
import { formatTimestamp, formatDuration } from "@/lib/utils";
import { cn } from "@/lib/utils";
import { useState } from "react";

export default function ActiveRunsPage() {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ["runs"],
    queryFn: listRuns,
    refetchInterval: 3000,
  });

  const [deleting, setDeleting] = useState<string | null>(null);

  const handleDelete = async (runId: string) => {
    setDeleting(runId);
    try {
      await deleteRun(runId);
      refetch();
    } finally {
      setDeleting(null);
    }
  };

  const runs = data?.runs ?? [];
  const running   = runs.filter((r) => r.status === "running");
  const queued    = runs.filter((r) => r.status === "queued");
  const completed = runs.filter((r) => r.status === "completed");
  const failed    = runs.filter((r) => r.status === "failed");

  return (
    <div className="p-4 space-y-4">
      {/* Header */}
      <div className="flex items-baseline justify-between">
        <div>
          <h1 className="text-[var(--accent)] text-sm tracking-[.15em]">ACTIVE RUNS</h1>
          <p className="text-[var(--text-muted)] text-[10px] tracking-[.08em] mt-0.5">
            {running.length} RUNNING · {queued.length} QUEUED · {completed.length} COMPLETED · {failed.length} FAILED
          </p>
        </div>
        <Link
          href="/runs/new"
          className="text-[10px] tracking-[.1em] px-4 py-1.5 bg-[var(--accent)] text-black hover:bg-[var(--accent-hover)] transition-colors"
        >
          + NEW RUN [F9]
        </Link>
      </div>

      {/* Stat row */}
      <div className="grid grid-cols-4 border border-[var(--border)]" style={{ gap: "1px", background: "var(--border)" }}>
        {[
          { label: "RUNNING",   value: running.length,   color: "text-[var(--accent)]" },
          { label: "QUEUED",    value: queued.length,    color: "text-[var(--warning)]" },
          { label: "COMPLETED", value: completed.length, color: "text-[var(--success)]" },
          { label: "FAILED",    value: failed.length,    color: failed.length > 0 ? "text-[var(--error)]" : "text-[var(--text-muted)]" },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-[var(--surface)] px-4 py-3">
            <div className="text-[var(--text-label)] text-[9px] tracking-[.1em] mb-1">{label}</div>
            <div className={cn("text-2xl tabular-nums", color)}>{value}</div>
          </div>
        ))}
      </div>

      {/* Table */}
      <div className="border border-[var(--border)]">
        <div
          className="grid bg-[var(--surface-2)] border-b border-[var(--border)] px-3 py-2"
          style={{ gridTemplateColumns: "2fr 2fr 90px 80px 110px 80px" }}
        >
          {["RUN ID", "UNIVERSE", "STATUS", "STAGE", "CREATED", ""].map((h) => (
            <span key={h} className="text-[var(--text-label)] text-[9px] tracking-[.1em]">{h}</span>
          ))}
        </div>

        {isLoading && (
          <div className="px-3 py-6 text-[var(--text-muted)] text-[11px] tracking-[.04em]">
            LOADING RUNS...
          </div>
        )}

        {!isLoading && runs.length === 0 && (
          <div className="px-3 py-8 text-center text-[var(--text-muted)] text-[11px] tracking-[.04em]">
            NO RUNS — <Link href="/runs/new" className="text-[var(--accent)]">INITIATE PIPELINE</Link>
          </div>
        )}

        {runs.map((run, i) => (
          <div
            key={run.run_id}
            className={cn(
              "grid px-3 py-2 border-b border-[var(--border-2)] items-center",
              i % 2 === 0 ? "bg-[var(--surface)]" : "bg-[var(--background)]",
              run.status === "running" && "bg-[var(--accent-faint)]"
            )}
            style={{ gridTemplateColumns: "2fr 2fr 90px 80px 110px 80px" }}
          >
            <Link
              href={`/runs/${run.run_id}`}
              className="text-[var(--accent)] text-[11px] hover:underline truncate pr-2"
            >
              {run.run_id.slice(0, 24)}
            </Link>
            <span className="text-[var(--text-secondary)] text-[11px] truncate pr-2">
              {run.universe.slice(0, 5).join(" · ")}
            </span>
            <span
              className={cn(
                "text-[10px] tracking-[.06em]",
                run.status === "running"   && "text-[var(--accent)]",
                run.status === "completed" && "text-[var(--success)]",
                run.status === "failed"    && "text-[var(--error)]",
                run.status === "queued"    && "text-[var(--warning)]",
              )}
            >
              {run.status === "running" && (
                <span className="stage-running mr-1">●</span>
              )}
              {run.status.toUpperCase()}
            </span>
            <span className="text-[var(--info)] text-[10px]">—</span>
            <span className="text-[var(--text-muted)] text-[10px]">
              {formatTimestamp(run.created_at)}
            </span>
            <button
              onClick={() => handleDelete(run.run_id)}
              disabled={deleting === run.run_id}
              className="text-[9px] tracking-[.06em] px-2 py-0.5 border border-[var(--border)] text-[var(--text-muted)] hover:border-[var(--error)] hover:text-[var(--error)] disabled:opacity-40 transition-colors"
            >
              {deleting === run.run_id ? "..." : "DEL"}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
