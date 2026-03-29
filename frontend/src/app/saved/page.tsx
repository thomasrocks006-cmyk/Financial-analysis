"use client";

import { useQuery } from "@tanstack/react-query";
import { listSavedRuns } from "@/lib/api";
import { formatTimestamp, formatNumber } from "@/lib/utils";
import { FileText, Download, Clock, CheckCircle2, XCircle } from "lucide-react";

export default function SavedRunsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["saved-runs"],
    queryFn: listSavedRuns,
  });

  const runs = data?.runs || [];

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-[var(--text-primary)]">
        Saved Runs ({runs.length})
      </h1>

      <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)]">
        <div className="divide-y divide-[var(--border)]">
          {isLoading ? (
            <div className="p-8 text-center text-sm text-[var(--text-muted)]">Loading…</div>
          ) : runs.length === 0 ? (
            <div className="p-8 text-center text-sm text-[var(--text-muted)]">
              No saved runs found.
            </div>
          ) : (
            runs.map((run) => (
              <div
                key={run.run_id}
                className="flex items-center justify-between px-4 py-4"
              >
                <div>
                  <div className="flex items-center gap-2">
                    {run.success ? (
                      <CheckCircle2 className="h-4 w-4 text-green-400" />
                    ) : (
                      <XCircle className="h-4 w-4 text-red-400" />
                    )}
                    <span className="text-sm font-mono font-medium text-[var(--text-primary)]">
                      {run.run_id}
                    </span>
                  </div>
                  <div className="mt-1 flex items-center gap-3 text-xs text-[var(--text-muted)]">
                    <span>{run.tickers.length} tickers</span>
                    <span>·</span>
                    <span>{run.model}</span>
                    <span>·</span>
                    <span>{formatNumber(run.word_count)} words</span>
                    {run.publication_status && (
                      <>
                        <span>·</span>
                        <span
                          className={
                            run.publication_status === "PASS"
                              ? "text-green-400"
                              : "text-red-400"
                          }
                        >
                          {run.publication_status}
                        </span>
                      </>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="flex items-center gap-1 text-xs text-[var(--text-muted)]">
                    <Clock className="h-3 w-3" />
                    {formatTimestamp(run.completed_at)}
                  </span>
                  {run.md_path && (
                    <a
                      href={`/api/v1/saved-runs/${run.run_id}`}
                      className="inline-flex items-center gap-1 rounded-lg border border-[var(--border)] px-2 py-1 text-xs text-[var(--text-secondary)] hover:bg-[var(--surface-2)]"
                    >
                      <Download className="h-3 w-3" />
                      JSON
                    </a>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
