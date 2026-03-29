"use client";

import { useQuery } from "@tanstack/react-query";
import { listRuns, listSavedRuns } from "@/lib/api";
import { MetricCard } from "@/components/ui/metric-card";
import {
  Activity,
  CheckCircle2,
  FileText,
  PlayCircle,
  BarChart3,
  Clock,
} from "lucide-react";
import Link from "next/link";
import { formatTimestamp } from "@/lib/utils";

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

  const runs = activeRuns?.runs || [];
  const saved = savedRuns?.runs || [];
  const running = runs.filter((r) => r.status === "running");
  const completed = runs.filter((r) => r.status === "completed");

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-[var(--text-primary)]">
          Dashboard
        </h1>
        <Link
          href="/runs/new"
          className="inline-flex items-center gap-2 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)]"
        >
          <PlayCircle className="h-4 w-4" />
          New Run
        </Link>
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Active Runs"
          value={running.length}
          icon={<Activity className="h-4 w-4" />}
          subtext={running.length > 0 ? "Pipeline executing" : "No runs in progress"}
        />
        <MetricCard
          label="Completed"
          value={completed.length}
          icon={<CheckCircle2 className="h-4 w-4" />}
          subtext="This session"
        />
        <MetricCard
          label="Saved Reports"
          value={saved.length}
          icon={<FileText className="h-4 w-4" />}
          subtext="On disk"
        />
        <MetricCard
          label="Total Runs"
          value={runs.length}
          icon={<BarChart3 className="h-4 w-4" />}
          subtext="All time this session"
        />
      </div>

      {/* Recent runs table */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)]">
        <div className="border-b border-[var(--border)] px-4 py-3">
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">
            Recent Runs
          </h2>
        </div>
        <div className="divide-y divide-[var(--border)]">
          {runs.length === 0 ? (
            <div className="p-8 text-center text-sm text-[var(--text-muted)]">
              No runs yet.{" "}
              <Link href="/runs/new" className="text-[var(--accent)] hover:underline">
                Start one
              </Link>
            </div>
          ) : (
            runs.slice(0, 10).map((run) => (
              <Link
                key={run.run_id}
                href={`/runs/${run.run_id}`}
                className="flex items-center justify-between px-4 py-3 transition-colors hover:bg-[var(--surface-2)]"
              >
                <div className="flex items-center gap-3">
                  <span className="text-sm font-mono text-[var(--text-secondary)]">
                    {run.run_id.slice(0, 16)}…
                  </span>
                  <span className="text-xs text-[var(--text-muted)]">
                    {run.universe.slice(0, 5).join(", ")}
                    {run.universe.length > 5 && ` +${run.universe.length - 5}`}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <span
                    className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                      run.status === "running"
                        ? "bg-blue-500/10 text-blue-400"
                        : run.status === "completed"
                        ? "bg-green-500/10 text-green-400"
                        : run.status === "failed"
                        ? "bg-red-500/10 text-red-400"
                        : "bg-gray-500/10 text-gray-400"
                    }`}
                  >
                    {run.status}
                  </span>
                  <span className="text-xs text-[var(--text-muted)]">
                    <Clock className="mr-1 inline h-3 w-3" />
                    {formatTimestamp(run.created_at)}
                  </span>
                </div>
              </Link>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
