"use client";

import { useQuery } from "@tanstack/react-query";
import { listRuns, listSavedRuns } from "@/lib/api";
import { MetricCard } from "@/components/ui/metric-card";
import { LiveEventFeed } from "@/components/pipeline/live-event-feed";
import Link from "next/link";
import { formatTimestamp } from "@/lib/utils";
import { cn } from "@/lib/utils";
import { usePipelineStore } from "@/lib/store";
import { getApiTargetLabel } from "@/lib/runtime-settings";

const MARKET_BOARD = [
  { sym: "SPX", value: "5421.8", pct: "+0.23%" },
  { sym: "NDX", value: "19284", pct: "+0.47%" },
  { sym: "ASX200", value: "7892.1", pct: "-0.23%" },
  { sym: "NVDA", value: "892.4", pct: "+2.41%" },
  { sym: "TSM", value: "164.2", pct: "+0.80%" },
  { sym: "VIX", value: "18.42", pct: "+4.78%" },
];

const QUICK_ACTIONS = [
  { href: "/runs/new", label: "INITIATE PIPELINE", detail: "Launch a new research run" },
  { href: "/runs", label: "ACTIVE RUNS", detail: "Monitor in-flight orchestration" },
  { href: "/saved", label: "SAVED REPORTS", detail: "Review completed packets" },
  { href: "/settings", label: "SETTINGS", detail: "Runtime URLs and defaults" },
];

const DESK_MODULES = [
  { label: "PORTFOLIO WORKBENCH", detail: "Open the dedicated portfolio blotter, watchlist, and allocation surface.", href: "/portfolio" },
  { label: "AUDIT CONSOLE", detail: "Inspect gates, blockers, quality score, and IC signals.", href: "/audit" },
  { label: "PROVENANCE MAP", detail: "Trace report sections back to stages, sources, and assumptions from run detail.", href: "/runs" },
  { label: "QUANT LAB", detail: "Review VaR, factor exposures, attribution, optimisation, and ESG context.", href: "/quant" },
];

const STARTUP_CHECKLIST = [
  "Verify the FastAPI backend target in Settings",
  "Review saved defaults for market, benchmark, and position limits",
  "Check prior saved reports before starting a fresh run",
  "Use New Run to select a preset universe or custom basket",
];

const PORTFOLIO_ROLES = ["CORE", "GROWTH", "HEDGE", "QUALITY", "TACTICAL", "INFRA"];

function statusColor(status: string) {
  if (status === "running")   return "text-[var(--accent)]";
  if (status === "completed") return "text-[var(--success)]";
  if (status === "failed")    return "text-[var(--error)]";
  return "text-[var(--text-muted)]";
}

export default function DashboardPage() {
  const store = usePipelineStore();
  const { data: activeRuns, error: runsError } = useQuery({
    queryKey: ["runs"],
    queryFn: listRuns,
    refetchInterval: 5000,
  });

  const { data: savedRuns, error: savedError } = useQuery({
    queryKey: ["saved-runs"],
    queryFn: listSavedRuns,
  });

  const runs  = activeRuns?.runs  || [];
  const saved = savedRuns?.runs   || [];
  const running   = runs.filter((r) => r.status === "running");
  const completed = runs.filter((r) => r.status === "completed");
  const failed    = runs.filter((r) => r.status === "failed");
  const hasApiError = Boolean(runsError || savedError);
  const watchlist = store.universe.slice(0, 8).map((ticker, index) => ({
    ticker,
    role: PORTFOLIO_ROLES[index % PORTFOLIO_ROLES.length],
    market: ticker.endsWith(".AX") ? "AU" : store.market.toUpperCase(),
    benchmark: store.benchmarkTicker,
    conviction: 88 - index * 4,
    readiness: index < 3 ? "READY" : index < 6 ? "WATCH" : "QUEUE",
  }));
  const operatorAlerts = [
    hasApiError
      ? "BACKEND API OFFLINE — CHECK SETTINGS OR START FASTAPI ON PORT 8000"
      : `API TARGET ONLINE — ${getApiTargetLabel().toUpperCase()}`,
    store.orchestrationMode === "auto"
      ? "MODEL POLICY: MERIDIAN AUTO ROUTING ACROSS MULTIPLE STAGES"
      : `MODEL POLICY: SINGLE MODEL OVERRIDE — ${store.model.toUpperCase()}`,
    activeRuns?.count
      ? `${activeRuns.count} RUNS TRACKED IN CURRENT SESSION`
      : "NO ACTIVE RUNS — USE NEW RUN TO START THE PIPELINE",
  ];

  return (
    <div className="space-y-0 divide-y divide-[var(--border)]">
      {/* Page header */}
      <div className="flex items-center justify-between px-4 py-3">
        <div>
          <span className="text-[var(--text-label)] text-[9px] tracking-[.12em] uppercase">
            Meridian Research Terminal
          </span>
          <div className="mt-1 text-[10px] tracking-[.08em] text-[var(--text-muted)] uppercase">
            AI Infrastructure Pipeline — JPAM AU Market
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="border border-[var(--border)] px-2 py-1 text-[10px] text-[var(--text-secondary)]">
            API: {getApiTargetLabel()}
          </span>
          <Link
            href="/runs/new"
            className="border border-[var(--accent)] px-3 py-1 text-[var(--accent)] text-[11px] tracking-[.06em] hover:bg-[var(--accent)] hover:text-black transition-colors"
          >
            + NEW RUN  [F9]
          </Link>
        </div>
      </div>

      {hasApiError && (
        <div className="border-y border-[var(--error)] bg-[var(--error-faint)] px-4 py-3 text-[11px] text-[var(--error)]">
          Backend data plane is offline. The frontend is running, but live runs and saved-run queries cannot load until the FastAPI server is up or the backend URL is corrected in Settings.
        </div>
      )}

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

      <div className="grid md:grid-cols-[1.3fr_1fr]" style={{ gap: "1px", background: "var(--border)" }}>
        <div className="bg-[var(--surface)]">
          <div className="px-4 py-1.5 bg-[var(--surface-2)]">
            <span className="text-[var(--text-label)] text-[9px] tracking-[.1em] uppercase">Quick Actions</span>
          </div>
          <div className="grid md:grid-cols-2">
            {QUICK_ACTIONS.map((item) => (
              <Link key={item.href} href={item.href} className="border border-[var(--border)] px-4 py-4 hover:bg-[var(--surface-2)] transition-colors">
                <div className="text-[10px] tracking-[.08em] text-[var(--accent)] uppercase">{item.label}</div>
                <div className="mt-2 text-[11px] text-[var(--text-secondary)]">{item.detail}</div>
              </Link>
            ))}
          </div>
        </div>
        <div className="bg-[var(--surface)]">
          <div className="px-4 py-1.5 bg-[var(--surface-2)]">
            <span className="text-[var(--text-label)] text-[9px] tracking-[.1em] uppercase">Run Defaults Snapshot</span>
          </div>
          <div className="px-4 py-3 space-y-2 text-[11px]">
            {[
              ["Model policy", store.orchestrationMode === "auto" ? "MERIDIAN AUTO ROUTING" : `SINGLE MODEL: ${store.model}`],
              ["Market", store.market.toUpperCase()],
              ["Benchmark", store.benchmarkTicker],
              ["Max positions", String(store.maxPositions)],
              ["Variants", store.portfolioVariants.join(" · ")],
            ].map(([label, value]) => (
              <div key={label} className="flex justify-between gap-3 border-b border-[var(--border-2)] py-1.5">
                <span className="text-[var(--text-label)] uppercase tracking-[.08em]">{label}</span>
                <span className="text-[var(--text-secondary)] text-right">{value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid md:grid-cols-[1.3fr_1fr]" style={{ gap: "1px", background: "var(--border)" }}>
        <div className="bg-[var(--surface)]">
          <div className="px-4 py-1.5 bg-[var(--surface-2)]">
            <span className="text-[var(--text-label)] text-[9px] tracking-[.1em] uppercase">Market Pulse</span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3">
            {MARKET_BOARD.map((item) => (
              <div key={item.sym} className="border border-[var(--border)] px-4 py-3">
                <div className="text-[10px] tracking-[.08em] text-[var(--info)] uppercase">{item.sym}</div>
                <div className="mt-1 text-[16px] text-[var(--text-primary)] tabular-nums">{item.value}</div>
                <div className={cn("mt-1 text-[10px] tabular-nums", item.pct.startsWith("+") ? "text-[var(--success)]" : "text-[var(--error)]")}>{item.pct}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="bg-[var(--surface)]">
          <div className="px-4 py-1.5 bg-[var(--surface-2)]">
            <span className="text-[var(--text-label)] text-[9px] tracking-[.1em] uppercase">Operator Readiness</span>
          </div>
          <div className="px-4 py-3 space-y-3 text-[11px] text-[var(--text-secondary)]">
            <div className="border border-[var(--border)] p-3">
              <div className="text-[10px] tracking-[.08em] text-[var(--accent)] uppercase">Before first run</div>
              <ul className="mt-2 space-y-1 list-disc pl-4">
                {STARTUP_CHECKLIST.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
            <div className="border border-[var(--border)] p-3">
              <div className="text-[10px] tracking-[.08em] text-[var(--accent)] uppercase">Current platform state</div>
              <div className="mt-2">Premium frontend is Bloomberg-styled, but still evolving toward the full multi-screen mockup with deeper report, audit, and provenance flows.</div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid xl:grid-cols-[1.2fr_1.1fr_0.8fr]" style={{ gap: "1px", background: "var(--border)" }}>
        <div className="bg-[var(--surface)]">
          <div className="px-4 py-1.5 bg-[var(--surface-2)]">
            <span className="text-[var(--text-label)] text-[9px] tracking-[.1em] uppercase">Portfolio Watchlist</span>
          </div>
          <div className="grid px-4 py-1 border-b border-[var(--border)]" style={{ gridTemplateColumns: "90px 90px 60px 90px 80px 70px" }}>
            {[
              "TICKER",
              "ROLE",
              "MKT",
              "BMK",
              "CONV",
              "STATE",
            ].map((hdr) => (
              <span key={hdr} className="text-[var(--text-muted)] text-[8px] tracking-[.08em]">{hdr}</span>
            ))}
          </div>
          {watchlist.map((row) => (
            <div key={row.ticker} className="grid px-4 py-2 border-b border-[var(--border)] hover:bg-[var(--surface-2)]" style={{ gridTemplateColumns: "90px 90px 60px 90px 80px 70px" }}>
              <span className="text-[10px] text-[var(--accent)]">{row.ticker}</span>
              <span className="text-[10px] text-[var(--text-secondary)]">{row.role}</span>
              <span className="text-[10px] text-[var(--text-secondary)]">{row.market}</span>
              <span className="text-[10px] text-[var(--text-muted)]">{row.benchmark}</span>
              <span className="text-[10px] tabular-nums text-[var(--text-primary)]">{row.conviction}</span>
              <span className={cn("text-[10px] tracking-[.06em]", row.readiness === "READY" ? "text-[var(--success)]" : row.readiness === "WATCH" ? "text-[var(--warning)]" : "text-[var(--text-muted)]")}>
                {row.readiness}
              </span>
            </div>
          ))}
        </div>

        <div className="bg-[var(--surface)]">
          <div className="px-4 py-1.5 bg-[var(--surface-2)]">
            <span className="text-[var(--text-label)] text-[9px] tracking-[.1em] uppercase">Live Tape</span>
          </div>
          <LiveEventFeed />
        </div>

        <div className="bg-[var(--surface)]">
          <div className="px-4 py-1.5 bg-[var(--surface-2)]">
            <span className="text-[var(--text-label)] text-[9px] tracking-[.1em] uppercase">Alerts & Queue</span>
          </div>
          <div className="px-4 py-3 space-y-3 text-[11px] text-[var(--text-secondary)]">
            <div className="border border-[var(--border)] p-3">
              <div className="text-[10px] tracking-[.08em] text-[var(--accent)] uppercase">Operator Alerts</div>
              <div className="mt-2 space-y-2">
                {operatorAlerts.map((alert) => (
                  <div key={alert} className="border-b border-[var(--border-2)] pb-2 last:border-0 last:pb-0">
                    {alert}
                  </div>
                ))}
              </div>
            </div>
            <div className="border border-[var(--border)] p-3">
              <div className="text-[10px] tracking-[.08em] text-[var(--accent)] uppercase">Recent Packet Queue</div>
              <div className="mt-2 space-y-2">
                {saved.slice(0, 4).length > 0 ? saved.slice(0, 4).map((run) => (
                  <Link key={run.run_id} href="/saved" className="block border-b border-[var(--border-2)] pb-2 last:border-0 last:pb-0 hover:text-[var(--accent)]">
                    <div className="text-[10px] text-[var(--text-primary)]">{run.run_id}</div>
                    <div className="mt-1 text-[10px] text-[var(--text-muted)]">{run.tickers.slice(0, 3).join(" · ")} · {run.publication_status}</div>
                  </Link>
                )) : (
                  <div className="text-[10px] text-[var(--text-muted)]">No saved packets yet.</div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="bg-[var(--surface)] border-y border-[var(--border)]">
        <div className="px-4 py-1.5 bg-[var(--surface-2)]">
          <span className="text-[var(--text-label)] text-[9px] tracking-[.1em] uppercase">Desk Modules</span>
        </div>
        <div className="grid md:grid-cols-2 xl:grid-cols-4">
          {DESK_MODULES.map((module) => (
            <Link
              key={module.label}
              href={module.href}
              className="border border-[var(--border)] px-4 py-4 hover:bg-[var(--surface-2)] transition-colors"
            >
              <div className="text-[10px] tracking-[.08em] text-[var(--accent)] uppercase">{module.label}</div>
              <div className="mt-2 text-[11px] text-[var(--text-secondary)]">{module.detail}</div>
            </Link>
          ))}
        </div>
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
              href="/saved"
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
