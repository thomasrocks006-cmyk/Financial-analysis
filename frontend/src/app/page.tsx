"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { listRuns, listSavedRuns, getMarketIndices, getMarketQuotes } from "@/lib/api";
import { MetricCard } from "@/components/ui/metric-card";
import { LiveEventFeed } from "@/components/pipeline/live-event-feed";
import Link from "next/link";
import { formatTimestamp } from "@/lib/utils";
import { cn } from "@/lib/utils";
import { usePipelineStore } from "@/lib/store";
import { getApiTargetLabel } from "@/lib/runtime-settings";
import {
  formatEventLabel,
  formatRunProgress,
  getBlockedStageLabel,
  getEventFreshnessMeta,
  getProgressBarTone,
  getRowActions,
  getRunProgressPercent,
  getRunStageLabel,
  statusColor,
  type RunFilter,
  type SortMode,
  getStatusRank,
} from "@/lib/run-summary";

// Market board now loaded live from the API.  This fallback is shown while
// the API call is in-flight or if the backend is offline.
const MARKET_BOARD_FALLBACK = [
  { sym: "SPY",  label: "S&P 500",      price: "—", change_pct_str: "—" },
  { sym: "QQQ",  label: "NASDAQ 100",   price: "—", change_pct_str: "—" },
  { sym: "IWM",  label: "Russell 2000", price: "—", change_pct_str: "—" },
  { sym: "EFA",  label: "Int'l Dev.",   price: "—", change_pct_str: "—" },
  { sym: "GLD",  label: "Gold",         price: "—", change_pct_str: "—" },
  { sym: "TLT",  label: "20yr Treasury",price: "—", change_pct_str: "—" },
  { sym: "IBIT", label: "Bitcoin ETF",  price: "—", change_pct_str: "—" },
  { sym: "USO",  label: "Crude Oil",    price: "—", change_pct_str: "—" },
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
  "Use New Run to select Discovery (broad market) or a named preset",
];

const PORTFOLIO_ROLES = ["CORE", "GROWTH", "HEDGE", "QUALITY", "TACTICAL", "INFRA"];

function formatQuotePrice(price: number | null | undefined) {
  if (price == null) return "—";
  return price >= 1000
    ? price.toLocaleString("en-US", { maximumFractionDigits: 0 })
    : price.toFixed(2);
}

export default function DashboardPage() {
  const store = usePipelineStore();
  const [runsFilter, setRunsFilter] = useState<RunFilter>("all");
  const [runsQuery, setRunsQuery] = useState("");
  const [runsSortMode, setRunsSortMode] = useState<SortMode>("recent");
  const { data: activeRuns, error: runsError } = useQuery({
    queryKey: ["runs"],
    queryFn: listRuns,
    refetchInterval: 5000,
  });

  const { data: savedRuns, error: savedError } = useQuery({
    queryKey: ["saved-runs"],
    queryFn: listSavedRuns,
  });

  // Live market indices — poll every 60 s (FMP free tier rate-limit friendly)
  const { data: indicesData } = useQuery({
    queryKey: ["market-indices"],
    queryFn: getMarketIndices,
    refetchInterval: 60_000,
    staleTime: 55_000,
    retry: 1,
  });

  const watchlistTickers = store.universe.slice(0, 8);

  const { data: watchlistQuotesData } = useQuery({
    queryKey: ["market-quotes", watchlistTickers],
    queryFn: () => getMarketQuotes(watchlistTickers),
    enabled: watchlistTickers.length > 0,
    refetchInterval: 60_000,
    staleTime: 55_000,
    retry: 1,
  });

  const marketBoard =
    indicesData?.indices && indicesData.indices.length > 0
      ? indicesData.indices.slice(0, 8).map((q) => ({
          sym: q.sym,
          label: q.label,
          price:
            q.price != null
              ? q.price >= 1000
                ? q.price.toLocaleString("en-US", { maximumFractionDigits: 0 })
                : q.price.toFixed(2)
              : "—",
          change_pct_str: q.change_pct_str ?? "—",
          positive: (q.change_pct ?? 0) >= 0,
        }))
      : MARKET_BOARD_FALLBACK.map((q) => ({
          ...q,
          positive: false,
        }));

  const runs  = activeRuns?.runs  || [];
  const saved = savedRuns?.runs   || [];
  const running   = runs.filter((r) => r.status === "running");
  const completed = runs.filter((r) => r.status === "completed");
  const failed    = runs.filter((r) => r.status === "failed");
  const hasApiError = Boolean(runsError || savedError);
  const watchlistQuoteMap = new Map(
    (watchlistQuotesData?.quotes ?? []).map((quote) => [quote.sym, quote])
  );
  const watchlist = watchlistTickers.map((ticker, index) => {
    const quote = watchlistQuoteMap.get(ticker);
    const hasQuote = quote && quote.price != null;
    return {
    ticker,
    role: PORTFOLIO_ROLES[index % PORTFOLIO_ROLES.length],
    last: formatQuotePrice(quote?.price),
    move: quote?.change_pct_str ?? "—",
    positive: (quote?.change_pct ?? 0) >= 0,
    market: ticker.endsWith(".AX") ? "AU" : store.market.toUpperCase(),
    benchmark: store.benchmarkTicker,
    conviction: 88 - index * 4,
    readiness: hasQuote ? (index < 3 ? "READY" : index < 6 ? "WATCH" : "QUEUE") : "PENDING",
  };
  });
  const quotedCount = watchlist.filter((row) => row.last !== "—").length;
  const positiveCount = watchlist.filter((row) => row.last !== "—" && row.positive).length;
  const strongestMover = [...watchlist]
    .filter((row) => row.move !== "—")
    .sort((a, b) => Math.abs(Number.parseFloat(b.move)) - Math.abs(Number.parseFloat(a.move)))[0];
  const operatorAlerts = [
    hasApiError
      ? "BACKEND API OFFLINE — CHECK SETTINGS OR START FASTAPI ON PORT 8000"
      : `API TARGET ONLINE — ${getApiTargetLabel().toUpperCase()}`,
    quotedCount > 0
      ? `WATCHLIST LIVE — ${quotedCount}/${watchlist.length} NAMES QUOTED · ${positiveCount} POSITIVE MOVERS`
      : "WATCHLIST QUOTES PENDING — MARKET DATA FEED OR FMP KEY MAY BE UNAVAILABLE",
    store.orchestrationMode === "auto"
      ? "MODEL POLICY: MERIDIAN AUTO ROUTING ACROSS MULTIPLE STAGES"
      : `MODEL POLICY: SINGLE MODEL OVERRIDE — ${store.model.toUpperCase()}`,
    activeRuns?.count
      ? `${activeRuns.count} RUNS TRACKED IN CURRENT SESSION`
      : "NO ACTIVE RUNS — USE NEW RUN TO START THE PIPELINE",
    strongestMover
      ? `LARGEST WATCHLIST MOVE — ${strongestMover.ticker} ${strongestMover.move}`
      : "NO WATCHLIST MOVER SIGNALS YET",
  ];
  const dashboardFilterOptions: Array<{ id: RunFilter; label: string; count: number }> = [
    { id: "all", label: "ALL", count: runs.length },
    { id: "running", label: "RUNNING", count: running.length },
    { id: "failed", label: "FAILED", count: failed.length },
    { id: "queued", label: "QUEUED", count: runs.filter((run) => run.status === "queued").length },
    { id: "completed", label: "COMPLETED", count: completed.length },
  ];
  const visibleRuns = useMemo(() => {
    const normalizedQuery = runsQuery.trim().toLowerCase();
    const filtered = runs.filter((run) => {
      if (runsFilter !== "all" && run.status !== runsFilter) return false;
      if (!normalizedQuery) return true;

      const haystack = [
        run.run_id,
        run.run_label || "",
        run.universe.join(" "),
        run.blocker_summary || "",
        run.last_event_label || "",
      ]
        .join(" ")
        .toLowerCase();

      return haystack.includes(normalizedQuery);
    });

    return [...filtered].sort((a, b) => {
      if (runsSortMode === "progress") {
        return (b.progress_pct ?? 0) - (a.progress_pct ?? 0);
      }
      if (runsSortMode === "updated") {
        return new Date(b.last_event_at || b.created_at).getTime() - new Date(a.last_event_at || a.created_at).getTime();
      }
      if (runsSortMode === "status") {
        return getStatusRank(a.status) - getStatusRank(b.status);
      }
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    });
  }, [runs, runsFilter, runsQuery, runsSortMode]);
  const visibleStaleRuns = visibleRuns.filter((run) => getEventFreshnessMeta(run).stale).length;
  const visibleBlockedRuns = visibleRuns.filter((run) => run.status === "failed").length;
  const visibleLiveRuns = visibleRuns.filter((run) => run.status === "running").length;

  return (
    <div className="space-y-0 divide-y divide-[var(--border)]">
      {/* Page header */}
      <div className="flex items-center justify-between px-4 py-3">
        <div>
          <span className="text-[var(--text-label)] text-[9px] tracking-[.12em] uppercase">
            Meridian Research Terminal
          </span>
          <div className="mt-1 text-[10px] tracking-[.08em] text-[var(--text-muted)] uppercase">
            Multi-Asset Research Platform — Broad Market Coverage
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
          <div className="px-4 py-1.5 bg-[var(--surface-2)] flex items-center justify-between">
            <span className="text-[var(--text-label)] text-[9px] tracking-[.1em] uppercase">Market Pulse</span>
            <span className="text-[9px] text-[var(--text-muted)]">
              {indicesData ? "LIVE · refreshes every 60s" : "LOADING…"}
            </span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4">
            {marketBoard.map((item) => (
              <div key={item.sym} className="border border-[var(--border)] px-4 py-3">
                <div className="text-[10px] tracking-[.08em] text-[var(--info)] uppercase">{item.sym}</div>
                <div className="text-[8px] text-[var(--text-muted)] uppercase mt-0.5">{item.label}</div>
                <div className="mt-1 text-[15px] text-[var(--text-primary)] tabular-nums">{item.price}</div>
                <div className={cn("mt-1 text-[10px] tabular-nums", item.positive ? "text-[var(--success)]" : "text-[var(--error)]")}>
                  {item.change_pct_str}
                </div>
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
              <div className="mt-2">Multi-asset Bloomberg-style terminal with live market data, broad cross-asset research coverage, and AI-driven universe discovery.</div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid xl:grid-cols-[1.2fr_1.1fr_0.8fr]" style={{ gap: "1px", background: "var(--border)" }}>
        <div className="bg-[var(--surface)]">
          <div className="px-4 py-1.5 bg-[var(--surface-2)]">
            <span className="text-[var(--text-label)] text-[9px] tracking-[.1em] uppercase">Portfolio Watchlist</span>
          </div>
          <div className="flex items-center justify-between px-4 py-1.5 border-b border-[var(--border)] text-[8px] tracking-[.08em] text-[var(--text-muted)]">
            <span>LIVE WATCHLIST SNAPSHOT</span>
            <span>{watchlistQuotesData?.source?.toUpperCase() ?? "SOURCE PENDING"}</span>
          </div>
          <div className="grid px-4 py-1 border-b border-[var(--border)]" style={{ gridTemplateColumns: "80px 90px 80px 80px 60px 70px" }}>
            {[
              "TICKER",
              "ROLE",
              "LAST",
              "MOVE",
              "MKT",
              "STATE",
            ].map((hdr) => (
              <span key={hdr} className="text-[var(--text-muted)] text-[8px] tracking-[.08em]">{hdr}</span>
            ))}
          </div>
          {watchlist.map((row) => (
            <div key={row.ticker} className="grid px-4 py-2 border-b border-[var(--border)] hover:bg-[var(--surface-2)]" style={{ gridTemplateColumns: "80px 90px 80px 80px 60px 70px" }}>
              <span className="text-[10px] text-[var(--accent)]">{row.ticker}</span>
              <span className="text-[10px] text-[var(--text-secondary)]">{row.role}</span>
              <span className="text-[10px] tabular-nums text-[var(--text-primary)]">{row.last}</span>
              <span className={cn("text-[10px] tabular-nums", row.move === "—" ? "text-[var(--text-muted)]" : row.positive ? "text-[var(--success)]" : "text-[var(--error)]")}>
                {row.move}
              </span>
              <span className="text-[10px] text-[var(--text-secondary)]">{row.market}</span>
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
        <div className="border-b border-[var(--border)] bg-[var(--surface)] px-4 py-3 space-y-3">
          <div className="grid gap-3 xl:grid-cols-[1.3fr_auto_auto] xl:items-end">
            <label className="block">
              <span className="mb-1 block text-[10px] tracking-[.08em] text-[var(--text-label)] uppercase">Search runs</span>
              <input
                value={runsQuery}
                onChange={(e) => setRunsQuery(e.target.value)}
                placeholder="Run ID, label, ticker, blocker, event…"
                className="w-full border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-[11px] text-[var(--text-primary)]"
              />
            </label>
            <div className="flex flex-wrap gap-1.5 xl:justify-end">
              {dashboardFilterOptions.map((option) => (
                <button
                  key={option.id}
                  onClick={() => setRunsFilter(option.id)}
                  className={cn(
                    "border px-2 py-1 text-[10px] tracking-[.08em] uppercase",
                    runsFilter === option.id
                      ? "border-[var(--accent)] bg-[var(--accent-faint)] text-[var(--accent)]"
                      : "border-[var(--border)] text-[var(--text-secondary)] hover:bg-[var(--surface-2)]"
                  )}
                >
                  {option.label} · {option.count}
                </button>
              ))}
            </div>
            <label className="block xl:w-[180px]">
              <span className="mb-1 block text-[10px] tracking-[.08em] text-[var(--text-label)] uppercase">Sort</span>
              <select
                value={runsSortMode}
                onChange={(e) => setRunsSortMode(e.target.value as SortMode)}
                className="w-full border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-[11px] text-[var(--text-primary)]"
              >
                <option value="recent">Newest first</option>
                <option value="updated">Last updated</option>
                <option value="progress">Highest progress</option>
                <option value="status">Status priority</option>
              </select>
            </label>
          </div>

          <div className="flex flex-wrap items-center gap-1.5 border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-[10px] tracking-[.08em] uppercase text-[var(--text-secondary)]">
            <span className="text-[var(--text-label)]">Desk ribbon</span>
            <span className="border border-[var(--accent)] px-2 py-0.5 text-[var(--accent)]">Visible {visibleRuns.length}</span>
            <span className="border border-[var(--accent)] px-2 py-0.5 text-[var(--accent)]">Live {visibleLiveRuns}</span>
            <span className="border border-[var(--error)] px-2 py-0.5 text-[var(--error)]">Blocked {visibleBlockedRuns}</span>
            <span className={cn("border px-2 py-0.5", visibleStaleRuns > 0 ? "border-[var(--warning)] text-[var(--warning)]" : "border-[var(--border)] text-[var(--text-muted)]")}>
              Stale {visibleStaleRuns}
            </span>
            <span className="border border-[var(--border)] px-2 py-0.5 text-[var(--text-muted)]">Sort {runsSortMode}</span>
          </div>
        </div>
        {/* Col headers */}
        <div
          className="grid px-4 py-1 border-b border-[var(--border)]"
          style={{ gridTemplateColumns: "2fr 2fr 90px 190px 110px" }}
        >
          {["RUN ID", "UNIVERSE", "STATUS", "STAGES", "CREATED"].map((hdr) => (
            <span key={hdr} className="text-[var(--text-muted)] text-[8px] tracking-[.08em]">{hdr}</span>
          ))}
        </div>

        {visibleRuns.length === 0 ? (
          <div className="px-4 py-6 text-[var(--text-muted)] text-[11px]">
            {runs.length === 0 ? (
              <>
                No runs yet — <Link href="/runs/new" className="text-[var(--accent)] hover:underline">initiate pipeline</Link>
              </>
            ) : (
              <>No runs match the current dashboard filters.</>
            )}
          </div>
        ) : (
          visibleRuns.slice(0, 12).map((run) => {
            const freshness = getEventFreshnessMeta(run);

            return <div
              key={run.run_id}
              className={cn(
                "grid px-4 py-2 border-b border-[var(--border)] transition-colors",
                run.status === "running" && "bg-[var(--accent-faint)]",
                run.status === "failed" && "bg-[var(--error-faint)]"
              )}
              style={{ gridTemplateColumns: "2fr 2fr 90px 190px 110px" }}
            >
              <Link href={`/runs/${run.run_id}`} className="min-w-0 hover:text-[var(--accent)]">
                <span className="block text-[10px] tabular-nums text-[var(--text-secondary)] truncate">
                  {run.run_id.slice(0, 20)}
                  {run.run_label && (
                    <span className="ml-2 text-[var(--text-muted)]">{run.run_label}</span>
                  )}
                </span>
                <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[9px] text-[var(--text-muted)]">
                  <span className="truncate">Last event: {formatEventLabel(run)}</span>
                  <span className={cn("border px-1.5 py-0.5 tracking-[.08em] uppercase", freshness.tone)}>
                    {freshness.label}
                  </span>
                  <span>{freshness.detail}</span>
                </div>
              </Link>
              <div className="min-w-0 text-[10px] text-[var(--text-muted)]">
                <div className="truncate">
                  {run.universe.slice(0, 5).join(" · ")}
                  {run.universe.length > 5 && ` +${run.universe.length - 5}`}
                </div>
                {(getBlockedStageLabel(run) || run.blocker_summary) && (
                  <span className={cn(
                    "mt-1 block truncate text-[9px]",
                    run.status === "failed" ? "text-[var(--error)]" : "text-[var(--warning)]"
                  )}>
                    {getBlockedStageLabel(run) ?? `${run.status === "failed" ? "Blocker" : "Watch"}: ${run.blocker_summary}`}
                  </span>
                )}
              </div>
              <div className="space-y-1">
                <span className={cn("block text-[10px] tracking-[.04em] uppercase", statusColor(run.status))}>
                  {run.status}
                </span>
                <div className="flex flex-wrap gap-1">
                  {getRowActions(run).map((action) => (
                    <Link
                      key={`${run.run_id}-${action.label}`}
                      href={action.href}
                      className="border border-[var(--border)] px-1.5 py-0.5 text-[8px] uppercase tracking-[.06em] text-[var(--text-secondary)] hover:border-[var(--accent)] hover:text-[var(--accent)]"
                    >
                      {action.label}
                    </Link>
                  ))}
                </div>
              </div>
              <div className="space-y-1">
                <div className="flex items-center justify-between gap-2 text-[10px] tabular-nums text-[var(--text-muted)]">
                  <span>{formatRunProgress(run)}</span>
                  <span>{Math.round(getRunProgressPercent(run))}%</span>
                </div>
                <div className="h-1 overflow-hidden rounded-full bg-[var(--border)]">
                  <div
                    className={cn("h-full rounded-full transition-all", getProgressBarTone(run.status))}
                    style={{ width: `${getRunProgressPercent(run)}%` }}
                  />
                </div>
                <div className={cn("truncate text-[9px]", run.status === "failed" ? "text-[var(--error)]" : "text-[var(--text-muted)]")}>
                  {getBlockedStageLabel(run) ?? getRunStageLabel(run)}
                </div>
              </div>
              <span className="text-[10px] tabular-nums text-[var(--text-muted)]">
                {formatTimestamp(run.created_at)}
              </span>
            </div>;
          })
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
