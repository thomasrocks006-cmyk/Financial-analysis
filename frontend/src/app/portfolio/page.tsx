"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { BriefcaseBusiness, FolderOpen, Radar, Target } from "lucide-react";
import { getQuant, getRunStatus, listRuns, listSavedRuns } from "@/lib/api";
import { usePipelineStore } from "@/lib/store";
import { formatTimestamp } from "@/lib/utils";
import { getApiTargetLabel } from "@/lib/runtime-settings";

const DESK_BUCKETS = ["CORE", "GROWTH", "QUALITY", "TACTICAL", "HEDGE", "INFRA"];

function convictionBand(index: number) {
  return Math.max(58, 92 - index * 4);
}

export default function PortfolioPage() {
  const store = usePipelineStore();
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const { data: activeRuns } = useQuery({ queryKey: ["runs"], queryFn: listRuns, refetchInterval: 5000 });
  const { data: savedRuns } = useQuery({ queryKey: ["saved-runs"], queryFn: listSavedRuns });

  const candidateRunId = selectedRunId || activeRuns?.runs[0]?.run_id || null;

  useEffect(() => {
    if (!selectedRunId && activeRuns?.runs?.[0]?.run_id) {
      setSelectedRunId(activeRuns.runs[0].run_id);
    }
  }, [activeRuns?.runs, selectedRunId]);

  const { data: selectedRun } = useQuery({
    queryKey: ["run-status", candidateRunId],
    queryFn: () => getRunStatus(candidateRunId as string),
    enabled: !!candidateRunId,
  });

  const { data: quantData } = useQuery({
    queryKey: ["quant", candidateRunId],
    queryFn: () => getQuant(candidateRunId as string),
    enabled: !!candidateRunId,
  });

  const backendWeights = quantData?.quant?.baseline_weights || {};
  const optimisationResults = quantData?.quant?.optimisation_results || {};
  const rebalanceProposal = (quantData?.quant?.rebalance_proposal || {}) as Record<string, unknown>;
  const attribution = (quantData?.quant?.attribution || {}) as Record<string, unknown>;
  const etfDifferentiationScore = quantData?.quant?.etf_differentiation_score;

  const blotterRows = useMemo(
    () =>
      store.universe.slice(0, 12).map((ticker, index) => {
        const backendWeight = Number(backendWeights[ticker] ?? 0);
        const resolvedWeight = backendWeight > 0 ? backendWeight * 100 : Math.max(3.2, 10.5 - index * 0.45);

        return {
        ticker,
        bucket: DESK_BUCKETS[index % DESK_BUCKETS.length],
        weight: resolvedWeight,
        conviction: convictionBand(index),
        benchmark: store.benchmarkTicker,
        market: ticker.endsWith(".AX") ? "AU" : store.market.toUpperCase(),
        state:
          backendWeight >= 0.09
            ? "ACTIVE"
            : backendWeight >= 0.05
            ? "WATCH"
            : index < store.maxPositions / 5
            ? "ACTIVE"
            : index < store.maxPositions / 3
            ? "WATCH"
            : "QUEUE",
        };
      }),
    [backendWeights, store.benchmarkTicker, store.market, store.maxPositions, store.universe],
  );

  const runningCount = activeRuns?.runs.filter((run) => run.status === "running").length || 0;
  const completedCount = activeRuns?.runs.filter((run) => run.status === "completed").length || 0;
  const packetQueue = savedRuns?.runs.slice(0, 5) || [];
  const selectedUniverse = selectedRun?.universe || [];
  const overlapCount = selectedUniverse.filter((ticker) => store.universe.includes(ticker)).length;
  const backendWeightCount = Object.keys(backendWeights).length;
  const rebalanceTrades = Array.isArray(rebalanceProposal.trades) ? rebalanceProposal.trades.length : 0;
  const optimisationObjective = String(optimisationResults.objective || "baseline_equal_weight").replaceAll("_", " ").toUpperCase();
  const improvementBps = Number(optimisationResults.improvement_bps ?? 0);
  const allocationEffect = Number(attribution.allocation_effect ?? 0);
  const selectionEffect = Number(attribution.selection_effect ?? 0);
  const selectedCompletionState =
    selectedRun?.status === "completed"
      ? "COMPLETE"
      : selectedRun?.status === "running"
      ? "LIVE"
      : selectedRun?.status === "failed"
      ? "FAILED"
      : "QUEUED";

  return (
    <div className="space-y-0 divide-y divide-[var(--border)]">
      <div className="flex items-center justify-between px-4 py-3">
        <div>
          <div className="text-[9px] uppercase tracking-[.12em] text-[var(--text-label)]">Portfolio Workbench</div>
          <div className="mt-1 text-[10px] uppercase tracking-[.08em] text-[var(--text-muted)]">
            Allocation blotter · benchmark framing · saved packet queue
          </div>
        </div>
        <div className="border border-[var(--border)] px-2 py-1 text-[10px] text-[var(--text-secondary)]">
          API: {getApiTargetLabel()}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-[1px] bg-[var(--border)] lg:grid-cols-4">
        {[
          ["WATCHLIST", String(store.universe.length), <Radar key="radar" className="h-4 w-4" />, "tickers in desk memory"],
          ["MAX POSITIONS", String(store.maxPositions), <Target key="target" className="h-4 w-4" />, store.portfolioVariants.join(" · ")],
          ["RUNNING", String(runningCount), <BriefcaseBusiness key="briefcase" className="h-4 w-4" />, "active orchestration"],
          ["PACKETS", String(packetQueue.length), <FolderOpen key="folder" className="h-4 w-4" />, "latest saved reports"],
        ].map(([label, value, icon, detail]) => (
          <div key={String(label)} className="bg-[var(--surface)] px-4 py-3">
            <div className="flex items-center justify-between text-[var(--text-label)]">
              <span className="text-[9px] uppercase tracking-[.1em]">{label}</span>
              {icon}
            </div>
            <div className="mt-2 text-[22px] text-[var(--text-primary)] tabular-nums">{value}</div>
            <div className="mt-1 text-[10px] text-[var(--text-muted)]">{detail}</div>
          </div>
        ))}
      </div>

      <div className="grid gap-[1px] bg-[var(--border)] xl:grid-cols-[1.35fr_0.85fr]">
        <div className="bg-[var(--surface)]">
          <div className="bg-[var(--surface-2)] px-4 py-1.5 text-[9px] uppercase tracking-[.1em] text-[var(--text-label)]">Portfolio Blotter</div>
          <div className="grid px-4 py-1 border-b border-[var(--border)] text-[8px] tracking-[.08em] text-[var(--text-muted)]" style={{ gridTemplateColumns: "110px 95px 70px 90px 80px 75px" }}>
            <span>TICKER</span>
            <span>BUCKET</span>
            <span>MKT</span>
            <span>BMK</span>
            <span>WEIGHT</span>
            <span>STATE</span>
          </div>
          {blotterRows.map((row) => (
            <div key={row.ticker} className="grid px-4 py-2 border-b border-[var(--border)] hover:bg-[var(--surface-2)] text-[10px]" style={{ gridTemplateColumns: "110px 95px 70px 90px 80px 75px" }}>
              <span className="text-[var(--accent)]">{row.ticker}</span>
              <span className="text-[var(--text-secondary)]">{row.bucket}</span>
              <span className="text-[var(--text-secondary)]">{row.market}</span>
              <span className="text-[var(--text-muted)]">{row.benchmark}</span>
              <span className="tabular-nums text-[var(--text-primary)]">{row.weight.toFixed(1)}%</span>
              <span className={row.state === "ACTIVE" ? "text-[var(--success)]" : row.state === "WATCH" ? "text-[var(--warning)]" : "text-[var(--text-muted)]"}>{row.state}</span>
            </div>
          ))}
        </div>

        <div className="bg-[var(--surface)]">
          <div className="bg-[var(--surface-2)] px-4 py-1.5 text-[9px] uppercase tracking-[.1em] text-[var(--text-label)]">Desk Notes</div>
          <div className="space-y-3 px-4 py-3 text-[11px] text-[var(--text-secondary)]">
            <div className="border border-[var(--border)] p-3">
              <div className="text-[10px] uppercase tracking-[.08em] text-[var(--accent)]">Run staging board</div>
              <div className="mt-2 space-y-2">
                {(activeRuns?.runs || []).length > 0 ? (
                  activeRuns?.runs.map((run) => (
                    <button
                      key={run.run_id}
                      onClick={() => setSelectedRunId(run.run_id)}
                      className={`block w-full border px-3 py-2 text-left hover:bg-[var(--surface-2)] ${candidateRunId === run.run_id ? "border-[var(--accent)] text-[var(--accent)]" : "border-[var(--border)] text-[var(--text-secondary)]"}`}
                    >
                      <div className="text-[10px] font-mono">{run.run_id}</div>
                      <div className="mt-1 text-[10px] text-[var(--text-muted)]">{run.status.toUpperCase()} · {run.universe.slice(0, 3).join(" · ")}</div>
                    </button>
                  ))
                ) : (
                  <div className="text-[10px] text-[var(--text-muted)]">No runs available yet.</div>
                )}
              </div>
            </div>

            <div className="border border-[var(--border)] p-3">
              <div className="text-[10px] uppercase tracking-[.08em] text-[var(--accent)]">Selected run overlay</div>
              {selectedRun ? (
                <div className="mt-2 space-y-1.5 text-[10px]">
                  <div>Run: <span className="text-[var(--text-primary)]">{selectedRun.run_id}</span></div>
                  <div>Status: <span className="text-[var(--text-primary)]">{selectedCompletionState}</span></div>
                  <div>Universe size: <span className="text-[var(--text-primary)]">{selectedUniverse.length}</span></div>
                  <div>Desk overlap: <span className="text-[var(--text-primary)]">{overlapCount} / {selectedUniverse.length || 0}</span></div>
                  <div>Weight source: <span className="text-[var(--text-primary)]">{backendWeightCount > 0 ? `STAGE 12 BASELINE (${backendWeightCount})` : "DEFAULT DESK MODEL"}</span></div>
                  <div>Started: <span className="text-[var(--text-primary)]">{selectedRun.started_at ? formatTimestamp(selectedRun.started_at) : "Pending"}</span></div>
                </div>
              ) : (
                <div className="mt-2 text-[10px] text-[var(--text-muted)]">Select a run to compare it against the current portfolio watchlist.</div>
              )}
            </div>

            <div className="border border-[var(--border)] p-3">
              <div className="text-[10px] uppercase tracking-[.08em] text-[var(--accent)]">Construction overlay</div>
              <div className="mt-2 grid grid-cols-2 gap-2 text-[10px]">
                <div className="border border-[var(--border-2)] px-2 py-2">
                  <div className="text-[var(--text-muted)] uppercase tracking-[.06em]">Objective</div>
                  <div className="mt-1 text-[var(--text-primary)]">{optimisationObjective}</div>
                </div>
                <div className="border border-[var(--border-2)] px-2 py-2">
                  <div className="text-[var(--text-muted)] uppercase tracking-[.06em]">Improvement</div>
                  <div className="mt-1 text-[var(--text-primary)] tabular-nums">{improvementBps.toFixed(0)} bps</div>
                </div>
                <div className="border border-[var(--border-2)] px-2 py-2">
                  <div className="text-[var(--text-muted)] uppercase tracking-[.06em]">Rebalance trades</div>
                  <div className="mt-1 text-[var(--text-primary)] tabular-nums">{rebalanceTrades}</div>
                </div>
                <div className="border border-[var(--border-2)] px-2 py-2">
                  <div className="text-[var(--text-muted)] uppercase tracking-[.06em]">ETF differentiation</div>
                  <div className="mt-1 text-[var(--text-primary)] tabular-nums">
                    {etfDifferentiationScore != null ? `${etfDifferentiationScore.toFixed(1)} / 100` : "—"}
                  </div>
                </div>
              </div>
              <div className="mt-2 border border-[var(--border-2)] px-2 py-2 text-[10px]">
                <div className="text-[var(--text-muted)] uppercase tracking-[.06em]">Attribution read-through</div>
                <div className="mt-1 text-[var(--text-secondary)]">
                  Allocation <span className="tabular-nums text-[var(--text-primary)]">{allocationEffect.toFixed(1)}</span>
                  {" · "}
                  Selection <span className="tabular-nums text-[var(--text-primary)]">{selectionEffect.toFixed(1)}</span>
                </div>
              </div>
            </div>

            <div className="border border-[var(--border)] p-3">
              <div className="text-[10px] uppercase tracking-[.08em] text-[var(--accent)]">Portfolio directives</div>
              <div className="mt-2 space-y-1.5">
                <div>Benchmark anchor: <span className="text-[var(--text-primary)]">{store.benchmarkTicker}</span></div>
                <div>Market scope: <span className="text-[var(--text-primary)]">{store.market.toUpperCase()}</span></div>
                <div>Variants: <span className="text-[var(--text-primary)]">{store.portfolioVariants.join(" · ")}</span></div>
                <div>Model policy: <span className="text-[var(--text-primary)]">{store.orchestrationMode === "auto" ? "MERIDIAN AUTO ROUTING" : `SINGLE MODEL — ${store.model}`}</span></div>
              </div>
            </div>

            <div className="border border-[var(--border)] p-3">
              <div className="text-[10px] uppercase tracking-[.08em] text-[var(--accent)]">Recent packet queue</div>
              <div className="mt-2 space-y-2">
                {packetQueue.length > 0 ? (
                  packetQueue.map((run) => (
                    <Link key={run.run_id} href="/saved" className="block border-b border-[var(--border-2)] pb-2 last:border-0 last:pb-0 hover:text-[var(--accent)]">
                      <div className="text-[10px] text-[var(--text-primary)]">{run.run_id}</div>
                      <div className="mt-1 text-[10px] text-[var(--text-muted)]">
                        {run.tickers.slice(0, 3).join(" · ")} · {run.publication_status} · {formatTimestamp(run.completed_at)}
                      </div>
                    </Link>
                  ))
                ) : (
                  <div className="text-[10px] text-[var(--text-muted)]">No saved packets yet.</div>
                )}
              </div>
            </div>

            <div className="border border-[var(--border)] p-3">
              <div className="text-[10px] uppercase tracking-[.08em] text-[var(--accent)]">Run conversion</div>
              <div className="mt-2 text-[10px] text-[var(--text-muted)]">
                {completedCount} completed runs are available to translate into saved research packets and portfolio variants.
              </div>
              <div className="mt-3 flex gap-2">
                <Link href="/runs/new" className="border border-[var(--accent)] px-2 py-1 text-[10px] text-[var(--accent)] hover:bg-[var(--accent)] hover:text-black">Launch run</Link>
                <Link href="/quant" className="border border-[var(--border)] px-2 py-1 text-[10px] text-[var(--text-secondary)] hover:bg-[var(--surface-2)]">Open quant</Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}