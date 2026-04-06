"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Shield, Vote, Workflow } from "lucide-react";
import { getAudit, getRunStatus, listRuns } from "@/lib/api";
import { usePipelineStore } from "@/lib/store";
import { formatTimestamp } from "@/lib/utils";

export default function AuditPage() {
  const { activeRunId } = usePipelineStore();
  const [selectedRunId, setSelectedRunId] = useState<string | null>(activeRunId);

  const { data: runsData } = useQuery({
    queryKey: ["runs"],
    queryFn: listRuns,
    refetchInterval: 5000,
  });

  const candidateRunId = selectedRunId || activeRunId || runsData?.runs[0]?.run_id || null;

  useEffect(() => {
    if (!selectedRunId && candidateRunId) {
      setSelectedRunId(candidateRunId);
    }
  }, [candidateRunId, selectedRunId]);

  const { data: runStatus } = useQuery({
    queryKey: ["run-status", candidateRunId],
    queryFn: () => getRunStatus(candidateRunId as string),
    enabled: !!candidateRunId,
  });

  const { data: auditData } = useQuery({
    queryKey: ["audit", candidateRunId],
    queryFn: () => getAudit(candidateRunId as string),
    enabled: !!candidateRunId,
  });

  const audit = auditData?.audit_packet;
  const gateSummary = useMemo(
    () => [
      { label: "PASSED", value: audit?.gates_passed?.length || 0, tone: "text-[var(--success)]" },
      { label: "FAILED", value: audit?.gates_failed?.length || 0, tone: "text-[var(--error)]" },
      { label: "BLOCKERS", value: audit?.blockers?.length || 0, tone: "text-[var(--warning)]" },
      { label: "QUALITY", value: audit ? audit.quality_score.toFixed(1) : "—", tone: "text-[var(--text-primary)]" },
    ],
    [audit],
  );

  return (
    <div className="space-y-0 divide-y divide-[var(--border)]">
      <div className="flex items-center justify-between px-4 py-3">
        <div>
          <div className="text-[9px] uppercase tracking-[.12em] text-[var(--text-label)]">Audit Console</div>
          <div className="mt-1 text-[10px] uppercase tracking-[.08em] text-[var(--text-muted)]">
            Gate review · claim quality · investment committee record
          </div>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={candidateRunId || ""}
            onChange={(event) => setSelectedRunId(event.target.value)}
            className="border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-[10px] text-[var(--text-primary)]"
          >
            {(runsData?.runs || []).map((run) => (
              <option key={run.run_id} value={run.run_id}>{run.run_id}</option>
            ))}
          </select>
          {candidateRunId && (
            <Link href={`/runs/${candidateRunId}`} className="border border-[var(--accent)] px-2 py-1 text-[10px] text-[var(--accent)] hover:bg-[var(--accent)] hover:text-black">
              Open run
            </Link>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-[1px] bg-[var(--border)] lg:grid-cols-4">
        {gateSummary.map((item) => (
          <div key={item.label} className="bg-[var(--surface)] px-4 py-3">
            <div className="text-[9px] uppercase tracking-[.1em] text-[var(--text-label)]">{item.label}</div>
            <div className={`mt-2 text-[22px] tabular-nums ${item.tone}`}>{item.value}</div>
          </div>
        ))}
      </div>

      <div className="grid gap-[1px] bg-[var(--border)] xl:grid-cols-[0.9fr_1.1fr_1fr]">
        <div className="bg-[var(--surface)]">
          <div className="bg-[var(--surface-2)] px-4 py-1.5 text-[9px] uppercase tracking-[.1em] text-[var(--text-label)]">Run Ledger</div>
          <div className="space-y-2 px-4 py-3 text-[11px] text-[var(--text-secondary)]">
            {candidateRunId ? (
              <>
                <div className="border border-[var(--border)] p-3">
                  <div className="text-[10px] uppercase tracking-[.08em] text-[var(--accent)]">Selected run</div>
                  <div className="mt-2 text-[var(--text-primary)]">{candidateRunId}</div>
                  <div className="mt-1 text-[10px] text-[var(--text-muted)]">
                    {runStatus?.run_label || "Untitled run"} · {runStatus?.created_at ? formatTimestamp(runStatus.created_at) : "Pending timestamp"}
                  </div>
                </div>
                <div className="border border-[var(--border)] p-3">
                  <div className="flex items-center gap-2 text-[10px] uppercase tracking-[.08em] text-[var(--accent)]"><Workflow className="h-3 w-3" /> Universe</div>
                  <div className="mt-2 text-[10px] text-[var(--text-secondary)]">{runStatus?.universe?.join(" · ") || "No universe loaded"}</div>
                </div>
                <div className="border border-[var(--border)] p-3">
                  <div className="flex items-center gap-2 text-[10px] uppercase tracking-[.08em] text-[var(--accent)]"><Shield className="h-3 w-3" /> Claim mix</div>
                  <div className="mt-2 space-y-1 text-[10px]">
                    <div>Pass: <span className="text-[var(--success)]">{audit?.pass_claims ?? 0}</span></div>
                    <div>Caveat: <span className="text-[var(--warning)]">{audit?.caveat_claims ?? 0}</span></div>
                    <div>Fail: <span className="text-[var(--error)]">{audit?.fail_claims ?? 0}</span></div>
                  </div>
                </div>
              </>
            ) : (
              <div className="text-[10px] text-[var(--text-muted)]">No runs available yet.</div>
            )}
          </div>
        </div>

        <div className="bg-[var(--surface)]">
          <div className="bg-[var(--surface-2)] px-4 py-1.5 text-[9px] uppercase tracking-[.1em] text-[var(--text-label)]">Gate Console</div>
          <div className="grid md:grid-cols-2">
            <div className="border border-[var(--border)] p-4">
              <div className="text-[10px] uppercase tracking-[.08em] text-[var(--success)]">Passed Gates</div>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {(audit?.gates_passed || []).length > 0 ? (audit?.gates_passed || []).map((gate) => (
                  <span key={gate} className="border border-[var(--border)] bg-[var(--success-faint)] px-2 py-1 text-[11px] text-[var(--success)] font-mono">S{gate}</span>
                )) : <span className="text-[10px] text-[var(--text-muted)]">No passed gates recorded.</span>}
              </div>
            </div>
            <div className="border border-[var(--border)] p-4">
              <div className="text-[10px] uppercase tracking-[.08em] text-[var(--error)]">Failed Gates</div>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {(audit?.gates_failed || []).length > 0 ? (audit?.gates_failed || []).map((gate) => (
                  <span key={gate} className="border border-[var(--border)] bg-[var(--error-faint)] px-2 py-1 text-[11px] text-[var(--error)] font-mono">S{gate}</span>
                )) : <span className="text-[10px] text-[var(--text-muted)]">No gate failures recorded.</span>}
              </div>
            </div>
          </div>
          <div className="border-t border-[var(--border)] p-4">
            <div className="flex items-center gap-2 text-[10px] uppercase tracking-[.08em] text-[var(--accent)]"><AlertTriangle className="h-3 w-3" /> Blockers</div>
            <div className="mt-2 space-y-2 text-[11px] text-[var(--text-secondary)]">
              {(audit?.blockers || []).length > 0 ? (audit?.blockers || []).map((blocker) => (
                <div key={blocker} className="border border-[var(--border)] px-3 py-2">{blocker}</div>
              )) : <div className="text-[10px] text-[var(--text-muted)]">No blockers recorded.</div>}
            </div>
          </div>
        </div>

        <div className="bg-[var(--surface)]">
          <div className="bg-[var(--surface-2)] px-4 py-1.5 text-[9px] uppercase tracking-[.1em] text-[var(--text-label)]">Investment Committee</div>
          <div className="space-y-3 px-4 py-3 text-[11px] text-[var(--text-secondary)]">
            <div className="border border-[var(--border)] p-3">
              <div className="flex items-center gap-2 text-[10px] uppercase tracking-[.08em] text-[var(--accent)]"><Vote className="h-3 w-3" /> Approval state</div>
              <div className="mt-2 text-[var(--text-primary)]">
                {audit?.ic_approved === true ? "APPROVED" : audit?.ic_approved === false ? "REJECTED" : "NOT RECORDED"}
              </div>
            </div>
            <div className="border border-[var(--border)] p-3">
              <div className="text-[10px] uppercase tracking-[.08em] text-[var(--accent)]">Vote breakdown</div>
              <div className="mt-2 space-y-1.5">
                {Object.entries(audit?.ic_vote_breakdown || {}).length > 0 ? Object.entries(audit?.ic_vote_breakdown || {}).map(([member, vote]) => (
                  <div key={member} className="flex items-center justify-between border-b border-[var(--border-2)] pb-1 last:border-0">
                    <span className="uppercase tracking-[.06em] text-[var(--text-secondary)]">{member}</span>
                    <span className="font-mono text-[var(--text-primary)]">{String(vote)}</span>
                  </div>
                )) : <div className="text-[10px] text-[var(--text-muted)]">No IC votes recorded.</div>}
              </div>
            </div>
            <div className="border border-[var(--border)] p-3">
              <div className="text-[10px] uppercase tracking-[.08em] text-[var(--accent)]">ESG exclusions</div>
              <div className="mt-2 text-[10px] text-[var(--text-secondary)]">
                {(audit?.esg_exclusions || []).length > 0 ? (audit?.esg_exclusions || []).join(" · ") : "No exclusions recorded."}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}