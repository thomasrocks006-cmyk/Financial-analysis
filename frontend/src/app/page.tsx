"use client";

import { useQuery } from "@tanstack/react-query";
import { listRuns, listSavedRuns } from "@/lib/api";
import { MetricCard } from "@/components/ui/metric-card";
import Link from "next/link";
import { formatTimestamp } from "@/lib/utils";
import { cn } from "@/lib/utils";

function statusColor(status: string) {
  if (status === "running")   return "text-[var(--accent)]";
  if (status === "completed") return "text-[var(--success)]";
  if (status === "failed")    return "text-[var(--error)]";
  return "text-[var(--text-muted)]";
}

export default function DashboardPage() {
  const { data: activeRuns } = useQuery({
    queryKey: ["runs"],
    queryFn: listRuns,
    refetchInterval: 5000,
  });

  const { data: savedRuns } = useQuery({
    queryKey: ["saved-runs"],
    queryFn: listSavedRuns,
  });

  const runs  = activeRuns?.runs  || [];
  const saved = savedRuns?.runs   || [];
  const running   = runs.filter((r) => r.status === "running");
  const completed = runs.filter((r) => r.status === "completed");
  const failed    = runs.filter((r) => r.status === "failed");

  return (
    <div className="space-y-0 divide-y divide-[var(--border)]">
      {/* Page header */}
      <div className="flex items-center justify-between px-4 py-3">
        <span className="text-[var(--text-label)] text-[9px] tracking-[.12em] uppercase">
          Meridian Research Terminal
        </span>
        <Link
          href="/runs/new"
          className="border border-[var(--accent)] px-3 py-1 text-[var(--accent)] text-[11px] tracking-[.06em] hover:bg-[var(--accent)] hover:text-black transition-colors"
        >
          + NEW RUN  [F9]
        </Link>
      </div>

      {/* Stat panels */}
      <div
        className="grid"
        style={{ gridTemplateColumns: "repeat(4, 1fr)", gap: "1px", background: "var(--border)" }}
      >
        <MetricCard label="RUNNING"       value={running.length}   valueColor={running.length > 0 ? "text-[var(--accent)]" : undefined} />
        <MetricCard label="COMPLETED"     value={completed.length} trend={completed.length > 0 ? "up" : "neutral"} />
        <MetricCard label="SAVED REPORTS" value={saved.length}     subtext="on disk" />
        <MetricCard label="FAILED"        value={failed.length}    valueColor={failed.length > 0 ? "text-[var(--error)]" : undefined} />
      </div>

      {/* Runs table */}
      <div>
        <div className="px-4 py-1.5 bg-[var(--surface-2)]">
          <span className="text-[var(--text-label)] text-[9px] tracking-[.1em] uppercase">
            Recent Runs
          </span>
        </div>
        {/* Col headers */}
        <div
          className="grid px-4 py-1 border-b border-[var(--border)]"
          style={{ gridTemplateColumns: "2fr 2fr 90px 90px 110px" }}
        >
          {["RUN ID", "UNIVERSE", "STATUS", "STAGES", "CREATED"].map((hdr) => (
            <span key={hdr} className="text-[var(--text-muted)] text-[8px] tracking-[.08em]">{hdr}</span>
          ))}
        </div>

        {runs.length === 0 ? (
          <div className="px-4 py-6 text-[var(--text-muted)] text-[11px]">
            No runs yet —{" "}
            <Link href="/runs/new" className="text-[var(--accent)] hover:underline">
              initiate pipeline
            </Link>
          </div>
        ) : (
          runs.slice(0, 12).map((run) => (
            <Link
              key={run.run_id}
              href={`/runs/${run.run_id}`}
              className={cn(
                "grid px-4 py-2 border-b border-[var(--border)] hover:bg-[var(--surface-2)] transition-colors",
                run.status === "running" && "bg-[var(--accent-faint)]"
              )}
              style={{ gridTemplateColumns: "2fr 2fr 90px 90px 110px" }}
            >
              <span className="text-[10px] tabular-nums text-[var(--text-secondary)] truncate">
                {run.run_id.slice(0, 20)}
              </span>
              <span className="text-[10px] text-[var(--text-muted)] truncate">
                {run.universe.slice(0, 5).join(" · ")}
                {run.universe.length > 5 && ` +${run.universe.length - 5}`}
              </span>
              <span className={cn("text-[10px] tracking-[.04em] uppercase", statusColor(run.status))}>
                {run.status}
              </span>
              <span className="text-[10px] tabular-nums text-[var(--text-muted)]">
                — / 15
              </span>
              <span className="text-[10px] tabular-nums text-[var(--text-muted)]">
                {formatTimestamp(run.created_at)}
              </span>
            </Link>
          ))
        )}
      </div>

      {/* Saved reports table */}
      {saved.length > 0 && (
        <div>
          <div className="px-4 py-1.5 bg-[var(--surface-2)]">
            <span className="text-[var(--text-label)] text-[9px] tracking-[.1em] uppercase">
              Saved Reports
            </span>
          </div>
          {saved.slice(0, 6).map((r) => (
            <Link
              key={r.run_id}
              href={`/saved/${r.run_id}`}
              className="grid px-4 py-2 border-b border-[var(--border)] hover:bg-[var(--surface-2)] transition-colors"
              style={{ gridTemplateColumns: "2fr 2fr 110px" }}
            >
              <span className="text-[10px] text-[var(--text-secondary)] truncate">{r.run_id.slice(0, 20)}</span>
              <span className="text-[10px] text-[var(--text-muted)] truncate">
                {r.tickers?.slice(0, 4).join(" · ")}
              </span>
              <span className="text-[10px] tabular-nums text-[var(--text-muted)]">
                {formatTimestamp(r.completed_at)}
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
