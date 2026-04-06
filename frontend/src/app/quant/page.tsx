"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { BarChart3, LineChart, Radar, Sigma } from "lucide-react";
import { getRunStatus, listRuns } from "@/lib/api";
import { QuantPanel } from "@/components/quant/quant-panel";
import { usePipelineStore } from "@/lib/store";
import { formatTimestamp } from "@/lib/utils";

function QuantPageContent() {
  const { activeRunId } = usePipelineStore();
  const searchParams = useSearchParams();
  const linkedRunId = searchParams.get("run_id");
  const [selectedRunId, setSelectedRunId] = useState<string | null>(linkedRunId || activeRunId);

  const { data: runsData } = useQuery({
    queryKey: ["runs"],
    queryFn: listRuns,
    refetchInterval: 5000,
  });

  const candidateRunId = selectedRunId || linkedRunId || activeRunId || runsData?.runs[0]?.run_id || null;

  useEffect(() => {
    if (linkedRunId) {
      setSelectedRunId(linkedRunId);
    }
  }, [linkedRunId]);

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

  const summary = useMemo(
    () => [
      ["RUN", candidateRunId || "—", <LineChart key="run" className="h-4 w-4" />, runStatus?.status || "pending"],
      ["UNIVERSE", String(runStatus?.universe?.length || 0), <Radar key="universe" className="h-4 w-4" />, "tickers under review"],
      ["STATUS", (runStatus?.status || "—").toUpperCase(), <Sigma key="status" className="h-4 w-4" />, runStatus?.created_at ? formatTimestamp(runStatus.created_at) : ""],
      ["SCREEN", "QUANT", <BarChart3 key="screen" className="h-4 w-4" />, "risk · attribution · optimisation"],
    ],
    [candidateRunId, runStatus],
  );

  return (
    <div className="space-y-0 divide-y divide-[var(--border)]">
      <div className="flex items-center justify-between px-4 py-3">
        <div>
          <div className="text-[9px] uppercase tracking-[.12em] text-[var(--text-label)]">Quant Lab</div>
          <div className="mt-1 text-[10px] uppercase tracking-[.08em] text-[var(--text-muted)]">
            VaR · factors · mandate compliance · rebalancing signals
          </div>
          {linkedRunId && (
            <div className="mt-2 flex items-center gap-2 text-[10px] text-[var(--text-muted)]">
              <span>Linked from run detail:</span>
              <Link href={`/runs/${linkedRunId}`} className="text-[var(--accent)] hover:underline">
                {linkedRunId}
              </Link>
            </div>
          )}
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

      <div className="grid grid-cols-2 gap-[1px] bg-[var(--border)] xl:grid-cols-4">
        {summary.map(([label, value, icon, detail]) => (
          <div key={String(label)} className="bg-[var(--surface)] px-4 py-3">
            <div className="flex items-center justify-between text-[var(--text-label)]">
              <span className="text-[9px] uppercase tracking-[.1em]">{label}</span>
              {icon}
            </div>
            <div className="mt-2 text-[18px] text-[var(--text-primary)] break-all">{value}</div>
            <div className="mt-1 text-[10px] text-[var(--text-muted)]">{detail}</div>
          </div>
        ))}
      </div>

      <div className="grid gap-[1px] bg-[var(--border)] xl:grid-cols-[0.82fr_1.18fr]">
        <div id="run-selector" className="bg-[var(--surface)] scroll-mt-24">
          <div className="bg-[var(--surface-2)] px-4 py-1.5 text-[9px] uppercase tracking-[.1em] text-[var(--text-label)]">Run Selector</div>
          <div className="space-y-2 px-4 py-3 text-[11px] text-[var(--text-secondary)]">
            {(runsData?.runs || []).length > 0 ? (runsData?.runs || []).map((run) => (
              <button
                key={run.run_id}
                onClick={() => setSelectedRunId(run.run_id)}
                className={`block w-full border px-3 py-3 text-left hover:bg-[var(--surface-2)] ${candidateRunId === run.run_id ? "border-[var(--accent)] text-[var(--accent)]" : "border-[var(--border)] text-[var(--text-secondary)]"}`}
              >
                <div className="text-[10px] font-mono">{run.run_id}</div>
                <div className="mt-1 text-[10px] text-[var(--text-muted)]">{run.status.toUpperCase()} · {run.universe.slice(0, 3).join(" · ")}</div>
              </button>
            )) : <div className="text-[10px] text-[var(--text-muted)]">No runs available yet.</div>}
          </div>
        </div>

        <div className="bg-[var(--surface)] px-4 py-4">
          {candidateRunId ? <QuantPanel runId={candidateRunId} /> : <div className="py-10 text-center text-sm text-[var(--text-muted)]">Select or create a run to populate quant analytics.</div>}
        </div>
      </div>
    </div>
  );
}

export default function QuantPage() {
  return (
    <Suspense fallback={<div className="px-4 py-6 text-sm text-[var(--text-muted)]">Loading quant lab…</div>}>
      <QuantPageContent />
    </Suspense>
  );
}