"use client";

import { useQuery } from "@tanstack/react-query";
import { listRuns, listSavedRuns } from "@/lib/api";
import Link from "next/link";
import { formatTimestamp } from "@/lib/utils";
import { cn } from "@/lib/utils";

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

  const runs      = activeRuns?.runs ?? [];
  const saved     = savedRuns?.runs ?? [];
  const running   = runs.filter((r) => r.status === "running");
  const completed = runs.filter((r) => r.status === "completed");
  const failed    = runs.filter((r) => r.status === "failed");

  return (
    <div className="p-4 space-y-4">

      {/* Header row */}
      <div className="flex items-baseline justify-between">
        <div>
          <h1 className="text-sm tracking-[.15em] text-[var(--accent)]">
            MERIDIAN RESEARCH TERMINAL
          </h1>
          <p className="text-[var(--text-muted)] text-[10px] tracking-[.08em] mt-0.5">
            AI INFRASTRUCTURE PIPELINE — JPAM AU MARKET
          </p>
        </div>
        <Link
          href="/runs/new"
          className="text-[10px] tracking-[.1em] px-4 py-1.5 bg-[var(--accent)] text-black hover:bg-[var(--accent-hover)] transition-colors"
        >
          + NEW RUN [F9]
        </Link>
      </div>

      {/* Stat panels */}
      <div className="grid grid-cols-4 border border-[var(--border)]" style={{ gap: "1px", background: "var(--border)" }}>
        {[
          { label: "ACTIVE RUNS",   value: running.length,   color: running.length > 0 ? "text-[var(--accent)]" : "text-[var(--text-primary)]" },
          { label: "COMPLETED",     value: completed.length, color: "text-[var(--success)]" },
          { label: "SAVED REPORTS", value: saved.length,     color: "text-[var(--text-primary)]" },
          { label: "FAILED",        value: failed.length,    color: failed.length > 0 ? "text-[var(--error)]" : "text-[var(--text-muted)]" },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-[var(--surface)] px-4 py-3">
            <div className="text-[var(--text-label)] text-[9px] tracking-[.1em] mb-2">{label}</div>
            <div className={cn("text-2xl tabular-nums", color)}>{value}</div>
          </div>
        ))}
      </div>

      {/* Run table */}
      <div className="border border-[var(--border)]">
        {/* Table header */}
        <div
          className="grid bg-[var(--surface-2)] border-b border-[var(--border)] px-3 py-2"
          style={{ gridTemplateColumns: "2fr 2fr 90px 90px 110px" }}
        >
          {["RUN ID", "UNIVERSE", "STATUS", "STAGE", "TIME"].map((h) => (
            <span key={h} className="text-[var(--text-label)] text-[9px] tracking-[.1em]">
              {h}
            </span>
          ))}
        </div>

        {/* Rows */}
        {runs.length === 0 ? (
          <div className="px-3 py-8 text-center text-[var(--text-muted)] text-[11px] tracking-[.04em]">
            NO RUNS YET —{" "}
            <Link href="/runs/new" className="text-[var(--accent)] hover:underline">
              INITIATE PIPELINE
            </Link>
          </div>
        ) : (
          runs.slice(0, 15).map((run, i) => (
            <Link
              key={run.run_id}
              href={`/runs/${run.run_id}`}
              className={cn(
                "grid px-3 py-2 border-b border-[var(--border-2)] transition-colors",
                "hover:bg-[var(--surface-2)]",
                run.status === "running" && "bg-[var(--accent-faint)]"
              )}
              style={{ gridTemplateColumns: "2fr 2fr 90px 90px 110px" }}
            >
              <span className="text-[var(--accent)] text-[11px] truncate pr-2">
                {run.run_id.slice(0, 24)}
              </span>
              <span className="text-[var(--text-secondary)] text-[11px] truncate pr-2">
                {run.universe.slice(0, 5).join(" · ")}
                {run.universe.length > 5 && ` +${run.universe.length - 5}`}
              </span>
              <span
                className={cn(
                  "text-[10px] tracking-[.06em]",
                  run.status === "running"   && "text-[var(--accent)]",
                  run.status === "completed" && "text-[var(--success)]",
                  run.status === "failed"    && "text-[var(--error)]",
                  run.status === "queued"    && "text-[var(--text-muted)]",
                )}
              >
                {run.status.toUpperCase()}
              </span>
              <span className="text-[var(--info)] text-[10px]">—</span>
              <span className="text-[var(--text-muted)] text-[10px]">
                {formatTimestamp(run.created_at)}
              </span>
            </Link>
          ))
        )}
      </div>

      {/* Saved reports table */}
      {saved.length > 0 && (
        <div className="border border-[var(--border)]">
          <div className="bg-[var(--surface-2)] border-b border-[var(--border)] px-3 py-2">
            <span className="text-[var(--accent)] text-[10px] tracking-[.1em]">
              SAVED REPORTS — {saved.length} RECORDS
            </span>
          </div>
          <div
            className="grid bg-[var(--surface-2)] border-b border-[var(--border-2)] px-3 py-1"
            style={{ gridTemplateColumns: "2fr 2fr 60px 80px 100px" }}
          >
            {["RUN ID", "UNIVERSE", "SCORE", "WORDS", "DATE"].map((h) => (
              <span key={h} className="text-[var(--text-label)] text-[9px] tracking-[.1em]">{h}</span>
            ))}
          </div>
          {saved.slice(0, 8).map((s, i) => (
            <div
              key={s.run_id}
              className={cn(
                "grid px-3 py-2 border-b border-[var(--border-2)]",
                i % 2 === 0 ? "bg-[var(--surface)]" : "bg-[var(--background)]"
              )}
              style={{ gridTemplateColumns: "2fr 2fr 60px 80px 100px" }}
            >
              <span className="text-[var(--accent)] text-[11px] truncate">{s.run_id.slice(0, 24)}</span>
              <span className="text-[var(--text-secondary)] text-[11px]">{s.tickers.join(" · ")}</span>
              <span className="text-[var(--success)] text-[11px] tabular-nums">
                {s.word_count > 0 ? "✓" : "—"}
              </span>
              <span className="text-[var(--text-primary)] text-[11px] tabular-nums">
                {s.word_count?.toLocaleString() ?? "—"}
              </span>
              <span className="text-[var(--text-muted)] text-[10px]">
                {formatTimestamp(s.completed_at)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
