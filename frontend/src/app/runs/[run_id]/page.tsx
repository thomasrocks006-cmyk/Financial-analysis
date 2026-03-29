"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { usePipelineStore } from "@/lib/store";
import {
  getRunStatus,
  getReport,
  getAudit,
  createEventStream,
  downloadReportPdf,
} from "@/lib/api";
import type { PipelineEvent } from "@/lib/types";
import { PipelineTracker } from "@/components/pipeline/pipeline-tracker";
import { LiveEventFeed } from "@/components/pipeline/live-event-feed";
import { MetricCard } from "@/components/ui/metric-card";
import { TimingChart } from "@/components/charts/timing-chart";
import { cn, formatDuration, formatTimestamp } from "@/lib/utils";
import {
  Activity,
  CheckCircle2,
  XCircle,
  Clock,
  FileText,
  BarChart3,
  ArrowLeft,
  Download,
  Shield,
  ChevronDown,
  GitBranch,
  TrendingDown,
  FileDown,
} from "lucide-react";
import Link from "next/link";
import { ProvenancePanel } from "@/components/provenance/provenance-panel";
import { QuantPanel } from "@/components/quant/quant-panel";

export default function RunDetailPage() {
  const params = useParams();
  const router = useRouter();
  const runId = params.run_id as string;
  const store = usePipelineStore();
  const [activeTab, setActiveTab] = useState<"live" | "report" | "audit" | "provenance" | "quant" | "stages">("live");
  const [showStageDetail, setShowStageDetail] = useState<number | null>(null);

  // Connect to SSE if this is the active run
  useEffect(() => {
    if (runId && store.activeRunId !== runId) {
      store.setRunStarted(runId);
      const cleanup = createEventStream(
        runId,
        (event) => {
          store.processEvent(event.data as unknown as PipelineEvent);
        },
        (error) => {
          console.error("SSE error:", error);
        }
      );
      return cleanup;
    }
  }, [runId]);

  // Poll run status
  const { data: runStatus } = useQuery({
    queryKey: ["run-status", runId],
    queryFn: () => getRunStatus(runId),
    refetchInterval: store.runStatus === "running" ? 3000 : false,
    enabled: !!runId,
  });

  // Fetch report when completed
  const { data: reportData } = useQuery({
    queryKey: ["report", runId],
    queryFn: () => getReport(runId),
    enabled: store.runStatus === "completed",
  });

  // Fetch audit when completed
  const { data: auditData } = useQuery({
    queryKey: ["audit", runId],
    queryFn: () => getAudit(runId),
    enabled: store.runStatus === "completed",
  });

  const completedStages = store.stages.filter((s) => s.status === "completed").length;
  const failedStages = store.stages.filter((s) => s.status === "failed").length;
  const timings: Record<string, number> = {};
  store.stages.forEach((s) => {
    if (s.duration_ms > 0) {
      timings[`stage_${s.stage_num}`] = s.duration_ms;
    }
  });

  const tabs = [
    { id: "live" as const, label: "Live Tracker", icon: Activity },
    { id: "report" as const, label: "Report", icon: FileText },
    { id: "audit" as const, label: "Audit & Quality", icon: Shield },
    { id: "provenance" as const, label: "Provenance", icon: GitBranch },
    { id: "quant" as const, label: "Quant Analytics", icon: TrendingDown },
    { id: "stages" as const, label: "Stage Detail", icon: BarChart3 },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.back()}
            className="rounded-lg p-1.5 text-[var(--text-muted)] hover:bg-[var(--surface-2)]"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div>
            <h1 className="text-lg font-bold text-[var(--text-primary)]">
              Run: {runId.slice(0, 20)}…
            </h1>
            <p className="text-xs text-[var(--text-muted)]">
              {runStatus?.run_label || "Untitled run"} ·{" "}
              {formatTimestamp(runStatus?.created_at || "")}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {store.runStatus === "running" && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-500/10 px-3 py-1 text-xs font-medium text-blue-400">
              <span className="stage-running h-2 w-2 rounded-full bg-blue-400" />
              Running
            </span>
          )}
          {store.runStatus === "completed" && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-green-500/10 px-3 py-1 text-xs font-medium text-green-400">
              <CheckCircle2 className="h-3 w-3" />
              Completed
            </span>
          )}
          {store.runStatus === "failed" && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-red-500/10 px-3 py-1 text-xs font-medium text-red-400">
              <XCircle className="h-3 w-3" />
              Failed
            </span>
          )}
        </div>
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <MetricCard
          label="Stages"
          value={`${completedStages}/15`}
          icon={<CheckCircle2 className="h-4 w-4" />}
          subtext={failedStages > 0 ? `${failedStages} failed` : "All gates passed"}
        />
        <MetricCard
          label="Duration"
          value={
            store.totalDurationMs
              ? formatDuration(store.totalDurationMs)
              : store.pipelineStartedAt
              ? "Running…"
              : "—"
          }
          icon={<Clock className="h-4 w-4" />}
        />
        <MetricCard
          label="Events"
          value={store.events.length}
          icon={<Activity className="h-4 w-4" />}
          subtext="Live events captured"
        />
        <MetricCard
          label="Report"
          value={reportData?.word_count ? `${reportData.word_count} words` : "—"}
          icon={<FileText className="h-4 w-4" />}
          subtext={reportData?.estimated_pages ? `~${reportData.estimated_pages} pages` : ""}
        />
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 border-b border-[var(--border)]">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={cn(
              "flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors",
              activeTab === id
                ? "border-[var(--accent)] text-[var(--accent)]"
                : "border-transparent text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === "live" && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
          <div className="lg:col-span-2">
            <PipelineTracker
              onStageClick={(n) => {
                setShowStageDetail(n);
                setActiveTab("stages");
              }}
            />
          </div>
          <div className="lg:col-span-3">
            <LiveEventFeed />
          </div>
        </div>
      )}

      {activeTab === "report" && (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6">
          {reportData?.report_markdown ? (
            <>
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-lg font-semibold text-[var(--text-primary)]">
                  Research Report
                </h2>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => {
                      const blob = new Blob([reportData.report_markdown], { type: "text/markdown" });
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement("a");
                      a.href = url;
                      a.download = `${runId}-report.md`;
                      a.click();
                      URL.revokeObjectURL(url);
                    }}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--surface-2)]"
                  >
                    <Download className="h-3 w-3" />
                    Download .md
                  </button>
                  <button
                    onClick={async () => {
                      try {
                        const blob = await downloadReportPdf(runId);
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement("a");
                        a.href = url;
                        a.download = `${runId}-report.pdf`;
                        a.click();
                        URL.revokeObjectURL(url);
                      } catch (err) {
                        console.error("PDF download failed:", err);
                      }
                    }}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--surface-2)]"
                  >
                    <FileDown className="h-3 w-3" />
                    Download PDF
                  </button>
                </div>
              </div>
              <div
                className="report-content prose prose-invert max-w-none"
                dangerouslySetInnerHTML={{ __html: markdownToHtml(reportData.report_markdown) }}
              />
            </>
          ) : store.runStatus === "running" ? (
            <div className="py-12 text-center text-sm text-[var(--text-muted)]">
              Report will appear here when the pipeline completes…
            </div>
          ) : (
            <div className="py-12 text-center text-sm text-[var(--text-muted)]">
              No report available for this run.
            </div>
          )}
        </div>
      )}

      {activeTab === "audit" && (
        <div className="space-y-6">
          {auditData?.audit_packet ? (
            <>
              {/* Quality score */}
              <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                <MetricCard
                  label="Quality Score"
                  value={`${(auditData.audit_packet.quality_score || 0).toFixed(1)}/10`}
                  icon={<Shield className="h-4 w-4" />}
                />
                <MetricCard
                  label="Gates Passed"
                  value={`${auditData.audit_packet.gates_passed?.length || 0}/15`}
                />
                <MetricCard
                  label="Total Claims"
                  value={auditData.audit_packet.total_claims || 0}
                  subtext={`${auditData.audit_packet.pass_claims || 0} pass, ${auditData.audit_packet.caveat_claims || 0} caveat, ${auditData.audit_packet.fail_claims || 0} fail`}
                />
                <MetricCard
                  label="IC Approved"
                  value={auditData.audit_packet.ic_approved === true ? "Yes" : auditData.audit_packet.ic_approved === false ? "No" : "N/A"}
                />
              </div>

              {/* Timing chart */}
              {Object.keys(timings).length > 0 && (
                <TimingChart timings={timings} />
              )}

              {/* Blockers */}
              {(auditData.audit_packet.blockers?.length || 0) > 0 && (
                <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-4">
                  <h3 className="mb-2 text-sm font-semibold text-red-400">Blockers</h3>
                  <ul className="space-y-1">
                    {auditData.audit_packet.blockers?.map((b: string, i: number) => (
                      <li key={i} className="text-sm text-red-300">• {b}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Agent outcomes */}
              <div className="grid grid-cols-2 gap-4">
                <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
                  <h3 className="mb-2 text-sm font-semibold text-green-400">
                    Agents Succeeded ({auditData.audit_packet.agents_succeeded?.length || 0})
                  </h3>
                  <div className="flex flex-wrap gap-1">
                    {auditData.audit_packet.agents_succeeded?.map((a: string, i: number) => (
                      <span key={i} className="rounded-md bg-green-500/10 px-2 py-0.5 text-xs text-green-400">
                        {a}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
                  <h3 className="mb-2 text-sm font-semibold text-red-400">
                    Agents Failed ({auditData.audit_packet.agents_failed?.length || 0})
                  </h3>
                  <div className="flex flex-wrap gap-1">
                    {auditData.audit_packet.agents_failed?.map((a: string, i: number) => (
                      <span key={i} className="rounded-md bg-red-500/10 px-2 py-0.5 text-xs text-red-400">
                        {a}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Raw packet */}
              <details className="rounded-xl border border-[var(--border)] bg-[var(--surface)]">
                <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-[var(--text-primary)]">
                  Raw Audit Packet
                </summary>
                <pre className="overflow-auto p-4 text-xs text-[var(--text-secondary)]">
                  {JSON.stringify(auditData.audit_packet, null, 2)}
                </pre>
              </details>
            </>
          ) : (
            <div className="py-12 text-center text-sm text-[var(--text-muted)]">
              {store.runStatus === "running"
                ? "Audit data will appear when the pipeline completes…"
                : "No audit data available."}
            </div>
          )}
        </div>
      )}

      {activeTab === "provenance" && (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6">
          {store.runStatus === "completed" || store.runStatus === "failed" ? (
            <ProvenancePanel runId={runId} />
          ) : (
            <div className="py-12 text-center text-sm text-[var(--text-muted)]">
              Provenance data will appear when the pipeline completes…
            </div>
          )}
        </div>
      )}

      {activeTab === "quant" && (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6">
          {store.runStatus === "completed" || store.runStatus === "failed" ? (
            <QuantPanel runId={runId} />
          ) : (
            <div className="py-12 text-center text-sm text-[var(--text-muted)]">
              Quant analytics will appear when the pipeline completes…
            </div>
          )}
        </div>
      )}

      {activeTab === "stages" && (
        <div className="space-y-4">
          {store.stages.map((stage) => (
            <details
              key={stage.stage_num}
              open={showStageDetail === stage.stage_num}
              className="rounded-xl border border-[var(--border)] bg-[var(--surface)]"
            >
              <summary className="flex cursor-pointer items-center justify-between px-4 py-3">
                <div className="flex items-center gap-3">
                  <span className="text-xs font-mono text-[var(--text-muted)]">
                    S{stage.stage_num}
                  </span>
                  <span className="text-sm font-medium text-[var(--text-primary)]">
                    {stage.label}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <span
                    className={cn(
                      "text-xs font-medium",
                      stage.status === "completed" && "text-green-400",
                      stage.status === "running" && "text-blue-400",
                      stage.status === "failed" && "text-red-400",
                      stage.status === "pending" && "text-gray-500"
                    )}
                  >
                    {stage.status}
                  </span>
                  {stage.duration_ms > 0 && (
                    <span className="text-xs text-[var(--text-muted)] tabular-nums">
                      {formatDuration(stage.duration_ms)}
                    </span>
                  )}
                  <ChevronDown className="h-4 w-4 text-[var(--text-muted)]" />
                </div>
              </summary>
              <div className="border-t border-[var(--border)] p-4">
                <div className="grid grid-cols-2 gap-4 text-xs">
                  <div>
                    <span className="text-[var(--text-muted)]">Status:</span>{" "}
                    <span className="text-[var(--text-secondary)]">{stage.status}</span>
                  </div>
                  <div>
                    <span className="text-[var(--text-muted)]">Duration:</span>{" "}
                    <span className="text-[var(--text-secondary)]">
                      {stage.duration_ms > 0 ? formatDuration(stage.duration_ms) : "—"}
                    </span>
                  </div>
                  {stage.agent_name && (
                    <div className="col-span-2">
                      <span className="text-[var(--text-muted)]">Agent:</span>{" "}
                      <span className="text-[var(--text-secondary)]">{stage.agent_name}</span>
                    </div>
                  )}
                </div>
                <div className="mt-3 text-xs text-[var(--text-muted)]">
                  Stage output data is available via the API endpoint.
                </div>
              </div>
            </details>
          ))}
        </div>
      )}
    </div>
  );
}

// Simple markdown-to-HTML converter (for report display)
function markdownToHtml(md: string): string {
  return md
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/^### (.+)$/gm, "<h3>$1</h3>")
    .replace(/^## (.+)$/gm, "<h2>$1</h2>")
    .replace(/^# (.+)$/gm, "<h1>$1</h1>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/`(.+?)`/g, "<code>$1</code>")
    .replace(/^- (.+)$/gm, "<li>$1</li>")
    .replace(/(<li>[\s\S]*<\/li>)/, "<ul>$1</ul>")
    .replace(/^---$/gm, "<hr />")
    .replace(/\n\n/g, "</p><p>")
    .replace(/^(.+)$/gm, (match) => {
      if (match.startsWith("<")) return match;
      return `<p>${match}</p>`;
    });
}
