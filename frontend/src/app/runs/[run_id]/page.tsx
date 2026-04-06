"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { usePipelineStore } from "@/lib/store";
import { marked } from "marked";
import {
  getRunStatus,
  getReport,
  getAudit,
  getStageDetail,
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
  ArrowUpRight,
} from "lucide-react";
import Link from "next/link";
import { ProvenancePanel } from "@/components/provenance/provenance-panel";
import { QuantPanel } from "@/components/quant/quant-panel";

type DeskShortcut = {
  href: string;
  label: string;
  detail: string;
};

function getDeskShortcuts(runId: string): DeskShortcut[] {
  return [
    {
      href: `/audit?run_id=${runId}#gate-console`,
      label: "AUDIT DESK",
      detail: "Open gate review, blockers, and IC vote context for this run.",
    },
    {
      href: `/quant?run_id=${runId}#run-selector`,
      label: "QUANT LAB",
      detail: "Jump into factor, VaR, attribution, and optimisation outputs.",
    },
    {
      href: `/portfolio?run_id=${runId}#construction-overlay`,
      label: "PORTFOLIO",
      detail: "Carry this run into the construction overlay and blotter workbench.",
    },
    {
      href: `/monitor?run_id=${runId}`,
      label: "MONITOR",
      detail: "Return to the terminal monitor with the current run in context.",
    },
  ];
}

function getStageDeskShortcuts(runId: string, stageNum: number): DeskShortcut[] {
  const shortcuts: Record<number, DeskShortcut[]> = {
    5: [
      {
        href: `/audit?run_id=${runId}#run-ledger`,
        label: "OPEN AUDIT LEDGER",
        detail: "Review claim mix and source posture for the evidence stage.",
      },
    ],
    9: [
      {
        href: `/quant?run_id=${runId}#run-selector`,
        label: "OPEN QUANT LAB",
        detail: "Inspect VaR, factor tilt, ETF overlap, and scenario outputs.",
      },
    ],
    10: [
      {
        href: `/audit?run_id=${runId}#gate-console`,
        label: "OPEN AUDIT DESK",
        detail: "Review red-team challenge posture alongside downstream blockers.",
      },
    ],
    11: [
      {
        href: `/audit?run_id=${runId}#gate-console`,
        label: "OPEN REVIEW GATES",
        detail: "Trace the publish gate decision and IC posture for this run.",
      },
    ],
    12: [
      {
        href: `/portfolio?run_id=${runId}#construction-overlay`,
        label: "OPEN CONSTRUCTION",
        detail: "Carry stage 12 outputs into portfolio sizing and rebalance review.",
      },
      {
        href: `/quant?run_id=${runId}#run-selector`,
        label: "OPEN QUANT OVERLAY",
        detail: "Cross-check optimisation and attribution against the same run.",
      },
    ],
    14: [
      {
        href: `/monitor?run_id=${runId}`,
        label: "OPEN MONITOR",
        detail: "Return to the terminal monitor and live run queue.",
      },
    ],
  };

  return shortcuts[stageNum] || [];
}

export default function RunDetailPage() {
  const params = useParams();
  const router = useRouter();
  const runId = params.run_id as string;
  const store = usePipelineStore();
  const [activeTab, setActiveTab] = useState<"live" | "report" | "audit" | "provenance" | "quant" | "stages">("live");
  const [showStageDetail, setShowStageDetail] = useState<number | null>(null);

  // Connect to SSE if this is the active run; reset store on unmount
  useEffect(() => {
    const { resetRun, setRunStarted, processEvent } = store;
    if (runId && store.activeRunId !== runId) {
      setRunStarted(runId);
      const cleanup = createEventStream(
        runId,
        (event) => {
          processEvent(event.data as unknown as PipelineEvent);
        },
        (error) => {
          console.error("SSE error:", error);
        }
      );
      return () => {
        cleanup();
        resetRun();
      };
    }
    return () => {
      resetRun();
    };
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

  const { data: selectedStageDetail, isLoading: stageDetailLoading } = useQuery({
    queryKey: ["stage-detail", runId, showStageDetail],
    queryFn: () => getStageDetail(runId, showStageDetail as number),
    enabled: !!runId && activeTab === "stages" && showStageDetail !== null,
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

  const auditPacket = auditData?.audit_packet;
  const gatePassCount = auditPacket?.gates_passed?.length || 0;
  const gateFailCount = auditPacket?.gates_failed?.length || 0;
  const icVotes = Object.entries(auditPacket?.ic_vote_breakdown || {});
  const deskShortcuts = getDeskShortcuts(runId);

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

      <div className="grid gap-[1px] bg-[var(--border)] md:grid-cols-[1.2fr_1fr]">
        <div className="bg-[var(--surface)]">
          <div className="px-4 py-1.5 bg-[var(--surface-2)]">
            <span className="text-[var(--text-label)] text-[9px] tracking-[.1em] uppercase">Operator Console</span>
          </div>
          <div className="grid md:grid-cols-4">
            {[
              ["LIVE TRACKER", "Monitor stage progression and event flow", "live"],
              ["REPORT", "Read markdown, export packets, review investment note", "report"],
              ["AUDIT", "Check IC gates, blockers, and claim quality", "audit"],
              ["PROVENANCE", "Trace section lineage and source coverage", "provenance"],
            ].map(([label, detail, tab]) => (
              <button
                key={String(label)}
                onClick={() => setActiveTab(tab as typeof activeTab)}
                className="border border-[var(--border)] px-4 py-4 text-left hover:bg-[var(--surface-2)] transition-colors"
              >
                <div className="text-[10px] tracking-[.08em] uppercase text-[var(--accent)]">{label}</div>
                <div className="mt-2 text-[11px] text-[var(--text-secondary)]">{detail}</div>
              </button>
            ))}
          </div>
        </div>
        <div className="bg-[var(--surface)]">
          <div className="px-4 py-1.5 bg-[var(--surface-2)]">
            <span className="text-[var(--text-label)] text-[9px] tracking-[.1em] uppercase">Run State Snapshot</span>
          </div>
          <div className="px-4 py-3 space-y-2 text-[11px]">
            {[
              ["Run label", runStatus?.run_label || "Untitled run"],
              ["Status", store.runStatus || "pending"],
              ["Universe", runStatus?.universe?.slice(0, 5).join(" · ") || "—"],
              ["Completed stages", `${completedStages}/15`],
              ["Events captured", String(store.events.length)],
            ].map(([label, value]) => (
              <div key={String(label)} className="flex justify-between gap-3 border-b border-[var(--border-2)] py-1.5">
                <span className="text-[var(--text-label)] uppercase tracking-[.08em]">{label}</span>
                <span className="text-[var(--text-secondary)] text-right">{value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid gap-[1px] bg-[var(--border)] lg:grid-cols-4">
        {deskShortcuts.map((shortcut) => (
          <Link
            key={shortcut.label}
            href={shortcut.href}
            className="bg-[var(--surface)] px-4 py-4 transition-colors hover:bg-[var(--surface-2)]"
          >
            <div className="flex items-center justify-between text-[10px] tracking-[.08em] uppercase text-[var(--accent)]">
              <span>{shortcut.label}</span>
              <ArrowUpRight className="h-3.5 w-3.5" />
            </div>
            <div className="mt-2 text-[11px] text-[var(--text-secondary)]">{shortcut.detail}</div>
          </Link>
        ))}
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
                className="report-content max-w-none"
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

              <div className="grid gap-[1px] bg-[var(--border)] lg:grid-cols-[1.15fr_0.85fr]">
                <div className="bg-[var(--surface)]">
                  <div className="px-4 py-1.5 bg-[var(--surface-2)]">
                    <span className="text-[var(--text-label)] text-[9px] tracking-[.1em] uppercase">Gate Console</span>
                  </div>
                  <div className="grid md:grid-cols-2">
                    <div className="border border-[var(--border)] p-4">
                      <div className="text-[10px] tracking-[.08em] uppercase text-[var(--success)]">Passed Gates ({gatePassCount})</div>
                      <div className="mt-3 flex flex-wrap gap-1.5">
                        {(auditPacket?.gates_passed || []).map((gate: number) => (
                          <span key={gate} className="border border-[var(--border)] bg-[var(--success-faint)] px-2 py-1 text-[11px] text-[var(--success)] font-mono">
                            S{gate}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div className="border border-[var(--border)] p-4">
                      <div className="text-[10px] tracking-[.08em] uppercase text-[var(--error)]">Failed Gates ({gateFailCount})</div>
                      <div className="mt-3 flex flex-wrap gap-1.5">
                        {(auditPacket?.gates_failed || []).length > 0 ? (auditPacket?.gates_failed || []).map((gate: number) => (
                          <span key={gate} className="border border-[var(--border)] bg-[var(--error-faint)] px-2 py-1 text-[11px] text-[var(--error)] font-mono">
                            S{gate}
                          </span>
                        )) : <span className="text-[11px] text-[var(--text-muted)]">No gate failures recorded.</span>}
                      </div>
                    </div>
                  </div>
                </div>
                <div className="bg-[var(--surface)]">
                  <div className="px-4 py-1.5 bg-[var(--surface-2)]">
                    <span className="text-[var(--text-label)] text-[9px] tracking-[.1em] uppercase">Investment Committee</span>
                  </div>
                  <div className="p-4 space-y-3">
                    <div className="border border-[var(--border)] p-3 text-[11px]">
                      <div className="text-[10px] tracking-[.08em] uppercase text-[var(--text-label)]">Approval state</div>
                      <div className="mt-2 text-[var(--text-primary)]">
                        {auditPacket?.ic_approved === true ? "APPROVED" : auditPacket?.ic_approved === false ? "REJECTED" : "NOT RECORDED"}
                      </div>
                    </div>
                    <div className="border border-[var(--border)] p-3 text-[11px]">
                      <div className="text-[10px] tracking-[.08em] uppercase text-[var(--text-label)]">Vote Breakdown</div>
                      {icVotes.length > 0 ? (
                        <div className="mt-2 space-y-1.5">
                          {icVotes.map(([member, vote]) => (
                            <div key={member} className="flex items-center justify-between border-b border-[var(--border-2)] pb-1">
                              <span className="text-[var(--text-secondary)] uppercase tracking-[.06em]">{member}</span>
                              <span className="text-[var(--text-primary)] font-mono">{String(vote)}</span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="mt-2 text-[var(--text-muted)]">No IC vote details recorded.</div>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {/* Blockers */}
              {(auditData.audit_packet.blockers?.length || 0) > 0 && (
                <div className="border border-[var(--error)] bg-[var(--error-faint)] p-4">
                  <h3 className="mb-2 text-[10px] tracking-[.1em] uppercase text-[var(--error)]">Blockers</h3>
                  <ul className="space-y-1">
                    {auditData.audit_packet.blockers?.map((b: string, i: number) => (
                      <li key={i} className="text-sm text-[var(--error)]">• {b}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Agent outcomes */}
              <div className="grid grid-cols-2 gap-4">
                <div className="border border-[var(--border)] bg-[var(--surface)] p-4">
                  <h3 className="mb-2 text-[10px] tracking-[.1em] uppercase text-[var(--success)]">
                    Agents Succeeded ({auditData.audit_packet.agents_succeeded?.length || 0})
                  </h3>
                  <div className="flex flex-wrap gap-1">
                    {auditData.audit_packet.agents_succeeded?.map((a: string, i: number) => (
                      <span key={i} className="border border-[var(--border)] bg-[var(--success-faint)] px-2 py-0.5 text-xs text-[var(--success)]">
                        {a}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="border border-[var(--border)] bg-[var(--surface)] p-4">
                  <h3 className="mb-2 text-[10px] tracking-[.1em] uppercase text-[var(--error)]">
                    Agents Failed ({auditData.audit_packet.agents_failed?.length || 0})
                  </h3>
                  <div className="flex flex-wrap gap-1">
                    {auditData.audit_packet.agents_failed?.map((a: string, i: number) => (
                      <span key={i} className="border border-[var(--border)] bg-[var(--error-faint)] px-2 py-0.5 text-xs text-[var(--error)]">
                        {a}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {(auditPacket?.esg_exclusions?.length || 0) > 0 && (
                <div className="border border-[var(--border)] bg-[var(--surface)] p-4">
                  <h3 className="mb-2 text-[10px] tracking-[.1em] uppercase text-[var(--warning)]">ESG Exclusions</h3>
                  <div className="flex flex-wrap gap-1.5">
                    {auditPacket?.esg_exclusions?.map((item: string, idx: number) => (
                      <span key={idx} className="border border-[var(--border)] px-2 py-1 text-[11px] text-[var(--warning)]">
                        {item}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Raw packet */}
              <details className="border border-[var(--border)] bg-[var(--surface)]">
                <summary className="cursor-pointer px-4 py-3 text-[10px] tracking-[.1em] uppercase text-[var(--text-label)]">
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
              <summary
                onClick={(event) => {
                  event.preventDefault();
                  setShowStageDetail((current) => current === stage.stage_num ? null : stage.stage_num);
                }}
                className="flex cursor-pointer items-center justify-between px-4 py-3"
              >
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
                  {showStageDetail === stage.stage_num && selectedStageDetail?.gate_reason && (
                    <div className="col-span-2">
                      <span className="text-[var(--text-muted)]">Gate reason:</span>{" "}
                      <span className="text-[var(--text-secondary)]">{selectedStageDetail.gate_reason}</span>
                    </div>
                  )}
                </div>
                {showStageDetail === stage.stage_num && (
                  <div className="mt-4 border border-[var(--border)] bg-[var(--surface-2)] p-3">
                    <div className="mb-2 text-[10px] tracking-[.08em] uppercase text-[var(--text-label)]">Stage output</div>
                    {stageDetailLoading ? (
                      <div className="text-xs text-[var(--text-muted)]">Loading output…</div>
                    ) : selectedStageDetail?.has_output ? (
                      <pre className="overflow-auto text-[11px] leading-5 text-[var(--text-secondary)]">
                        {JSON.stringify(selectedStageDetail.output, null, 2)}
                      </pre>
                    ) : (
                      <div className="text-xs text-[var(--text-muted)]">No structured output was persisted for this stage.</div>
                    )}
                  </div>
                )}
                {showStageDetail === stage.stage_num && getStageDeskShortcuts(runId, stage.stage_num).length > 0 && (
                  <div className="mt-4 grid gap-2 lg:grid-cols-2">
                    {getStageDeskShortcuts(runId, stage.stage_num).map((shortcut) => (
                      <Link
                        key={`${stage.stage_num}-${shortcut.label}`}
                        href={shortcut.href}
                        className="border border-[var(--border)] bg-[var(--surface-2)] px-3 py-3 text-left transition-colors hover:bg-[var(--surface)]"
                      >
                        <div className="flex items-center justify-between text-[10px] tracking-[.08em] uppercase text-[var(--accent)]">
                          <span>{shortcut.label}</span>
                          <ArrowUpRight className="h-3.5 w-3.5" />
                        </div>
                        <div className="mt-2 text-[11px] text-[var(--text-secondary)]">{shortcut.detail}</div>
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            </details>
          ))}
        </div>
      )}
    </div>
  );
}

// Proper markdown-to-HTML using marked (handles tables, nested lists, code blocks)
function markdownToHtml(md: string): string {
  try {
    const result = marked.parse(md, { async: false });
    return result as string;
  } catch {
    // Fallback: return escaped plaintext
    return `<pre>${md.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")}</pre>`;
  }
}
