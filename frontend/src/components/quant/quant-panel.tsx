"use client";

import { useQuery } from "@tanstack/react-query";
import { getQuant } from "@/lib/api";
import type { QuantData } from "@/lib/types";
import { MetricCard } from "@/components/ui/metric-card";
import {
  TrendingDown,
  Layers,
  Target,
  Building2,
  Scale,
  Leaf,
  BarChart3,
  CheckCircle2,
  XCircle,
  AlertTriangle,
} from "lucide-react";

interface QuantPanelProps {
  runId: string;
}

export function QuantPanel({ runId }: QuantPanelProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["quant", runId],
    queryFn: () => getQuant(runId),
  });

  if (isLoading) {
    return (
      <div className="py-10 text-center text-sm text-[var(--text-muted)]">
        Loading quant analytics…
      </div>
    );
  }

  if (error || !data?.quant) {
    return (
      <div className="py-10 text-center text-sm text-[var(--text-muted)]">
        No quant analytics data available for this run.
      </div>
    );
  }

  const q: QuantData = data.quant;
  const hasAnyData =
    Object.keys(q.var_analysis || {}).length > 0 ||
    q.portfolio_volatility > 0 ||
    Object.keys(q.etf_overlap || {}).length > 0 ||
    (q.factor_exposures || []).length > 0 ||
    Object.keys(q.ic_record || {}).length > 0 ||
    Object.keys(q.attribution || {}).length > 0 ||
    (q.esg_scores || []).length > 0 ||
    Object.keys(q.baseline_weights || {}).length > 0;

  if (!hasAnyData) {
    return (
      <div className="space-y-4 py-6 text-center">
        <BarChart3 className="mx-auto h-10 w-10 text-[var(--text-muted)]" />
        <p className="text-sm text-[var(--text-muted)]">
          Quant analytics are generated from pipeline Stage 9 (Risk Assessment),
          Stage 12 (Portfolio Construction), and Stage 14 (Monitoring).
          Run the pipeline to populate this view.
        </p>
      </div>
    );
  }

  const varD = q.var_analysis || {};
  const ddD = q.drawdown_analysis || {};

  return (
    <div className="space-y-8">


      {(Object.keys(varD).length > 0 || q.portfolio_volatility > 0) && (
        <Section icon={<TrendingDown className="h-4 w-4" />} title="Market Risk Metrics">
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <MetricCard
              label="VaR 95% (1-day)"
              value={`${(varD.var_pct ?? 0).toFixed(2)}%`}
              icon={<TrendingDown className="h-4 w-4" />}
            />
            <MetricCard
              label="CVaR 95% (1-day)"
              value={`${(varD.cvar_pct ?? 0).toFixed(2)}%`}
              icon={<TrendingDown className="h-4 w-4" />}
            />
            <MetricCard
              label="Max Drawdown"
              value={`${(ddD.max_drawdown_pct ?? 0).toFixed(2)}%`}
              icon={<TrendingDown className="h-4 w-4" />}
            />
            <MetricCard
              label="Portfolio Volatility"
              value={`${(q.portfolio_volatility * 100).toFixed(2)}%`}
              icon={<TrendingDown className="h-4 w-4" />}
            />
          </div>
          {q.var_method && (
            <p className="mt-2 text-xs text-[var(--text-muted)]">
              Method: <span className="font-medium text-[var(--text-secondary)]">{q.var_method}</span>
              {" · "}Confidence: <span className="font-medium text-[var(--text-secondary)]">
                {((q.confidence_level ?? 0.95) * 100).toFixed(0)}%
              </span>
            </p>
          )}
        </Section>
      )}


      {(q.etf_differentiation_score != null || Object.keys(q.etf_overlap || {}).length > 0) && (
        <Section icon={<Layers className="h-4 w-4" />} title="ETF Overlap & Differentiation">
          {q.etf_differentiation_score != null && (
            <div className="mb-4 flex items-center gap-3">
              <span className="text-sm text-[var(--text-muted)]">Differentiation Score:</span>
              <span
                className={`text-lg font-bold ${
                  q.etf_differentiation_score >= 70
                    ? "text-green-400"
                    : q.etf_differentiation_score >= 40
                    ? "text-yellow-400"
                    : "text-red-400"
                }`}
              >
                {q.etf_differentiation_score.toFixed(1)} / 100
              </span>
              {q.etf_differentiation_score < 40 && (
                <span className="flex items-center gap-1 rounded-full bg-red-500/10 px-2 py-0.5 text-xs text-red-400">
                  <AlertTriangle className="h-3 w-3" />
                  Low active share
                </span>
              )}
              {q.etf_differentiation_score >= 70 && (
                <span className="flex items-center gap-1 rounded-full bg-green-500/10 px-2 py-0.5 text-xs text-green-400">
                  <CheckCircle2 className="h-3 w-3" />
                  Well differentiated
                </span>
              )}
            </div>
          )}
          <EtfOverlapTable etfOverlap={q.etf_overlap} />
        </Section>
      )}


      {(q.factor_exposures || []).length > 0 && (
        <Section icon={<Target className="h-4 w-4" />} title="Factor Exposures">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-[var(--border)]">
                  {["Ticker", "β Market", "β Size", "β Value", "β Momentum", "β Quality"].map((h) => (
                    <th key={h} className="px-3 py-2 text-left font-medium text-[var(--text-muted)]">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {q.factor_exposures.map((fe, i) => (
                  <tr key={i} className="hover:bg-[var(--surface-2)]">
                    <td className="px-3 py-2 font-mono font-medium text-[var(--text-primary)]">
                      {String(fe.ticker ?? "—")}
                    </td>
                    <td className="px-3 py-2 tabular-nums text-[var(--text-secondary)]">
                      {Number(fe.market_beta ?? 0).toFixed(2)}
                    </td>
                    <td className="px-3 py-2 tabular-nums text-[var(--text-secondary)]">
                      {Number(fe.size_loading ?? 0).toFixed(2)}
                    </td>
                    <td className="px-3 py-2 tabular-nums text-[var(--text-secondary)]">
                      {Number(fe.value_loading ?? 0).toFixed(2)}
                    </td>
                    <td className="px-3 py-2 tabular-nums text-[var(--text-secondary)]">
                      {Number(fe.momentum_loading ?? 0).toFixed(2)}
                    </td>
                    <td className="px-3 py-2 tabular-nums text-[var(--text-secondary)]">
                      {Number(fe.quality_loading ?? 0).toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {Object.keys(q.portfolio_factor_exposure || {}).length > 0 && (
            <p className="mt-2 text-xs text-[var(--text-muted)]">
              Portfolio composite —{" "}
              {["market_beta", "size_loading", "momentum_loading"]
                .map((k) => `β(${k.replace("_loading", "")})=${Number(q.portfolio_factor_exposure[k] ?? 0).toFixed(2)}`)
                .join("  ")}
            </p>
          )}
        </Section>
      )}


      {Object.keys(q.ic_record || {}).length > 0 && (
        <Section icon={<Building2 className="h-4 w-4" />} title="Investment Committee">
          <IcRecord record={q.ic_record} />
        </Section>
      )}


      {Object.keys(q.mandate_compliance || {}).length > 0 && (
        <Section icon={<Scale className="h-4 w-4" />} title="Mandate Compliance">
          <MandateCompliance mandate={q.mandate_compliance} />
        </Section>
      )}


      {(q.esg_scores || []).length > 0 && (
        <Section icon={<Leaf className="h-4 w-4" />} title="ESG Analytics">
          <EsgPanel scores={q.esg_scores} />
        </Section>
      )}


      {Object.keys(q.baseline_weights || {}).length > 0 && (
        <Section icon={<BarChart3 className="h-4 w-4" />} title="Portfolio Weights (Baseline — Equal Weight)">
          <div className="flex flex-wrap gap-3">
            {Object.entries(q.baseline_weights)
              .sort(([, a], [, b]) => b - a)
              .map(([ticker, weight]) => (
                <div
                  key={ticker}
                  className="flex min-w-[80px] flex-col items-center rounded-lg border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2"
                >
                  <span className="text-sm font-bold text-[var(--text-primary)]">{ticker}</span>
                  <span className="text-xs text-[var(--text-secondary)]">
                    {(weight * 100).toFixed(1)}%
                  </span>
                </div>
              ))}
          </div>
        </Section>
      )}


      {Object.keys(q.optimisation_results || {}).length > 0 && (
        <Section icon={<Target className="h-4 w-4" />} title="Portfolio Optimisation">
          <OptimisationPanel
            optResults={q.optimisation_results}
            baselineWeights={q.baseline_weights}
          />
        </Section>
      )}


      {!!(q.rebalance_proposal && (q.rebalance_proposal as Record<string, unknown>).trades) && (
        <Section icon={<Scale className="h-4 w-4" />} title="Rebalancing Signals">
          <RebalancePanel rebalData={q.rebalance_proposal as Record<string, unknown>} />
        </Section>
      )}


      {Object.keys(q.attribution || {}).length > 0 && (
        <Section icon={<BarChart3 className="h-4 w-4" />} title="Performance Attribution (Brinson-Hood-Beebower)">
          <AttributionPanel attribution={q.attribution} />
        </Section>
      )}

    </div>
  );
}

// ── Sub-components ──────────────────────────────────────────────────────────

function Section({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5">
      <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]">
        <span className="text-[var(--accent)]">{icon}</span>
        {title}
      </h3>
      {children}
    </div>
  );
}

function EtfOverlapTable({ etfOverlap }: { etfOverlap: Record<string, unknown> }) {
  const overlaps =
    (etfOverlap as Record<string, unknown>)?.overlaps ||
    (etfOverlap as Record<string, unknown>)?.etf_overlaps ||
    {};
  const rows = Object.entries(overlaps as Record<string, unknown>);
  if (!rows.length) return null;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-[var(--border)]">
            <th className="px-3 py-2 text-left font-medium text-[var(--text-muted)]">ETF</th>
            <th className="px-3 py-2 text-left font-medium text-[var(--text-muted)]">Overlap %</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--border)]">
          {rows.map(([etf, pct]) => (
            <tr key={etf} className="hover:bg-[var(--surface-2)]">
              <td className="px-3 py-2 font-mono text-[var(--text-primary)]">{etf}</td>
              <td className="px-3 py-2 tabular-nums text-[var(--text-secondary)]">
                {typeof pct === "number" ? `${pct.toFixed(1)}%` : String(pct)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function IcRecord({ record }: { record: Record<string, unknown> }) {
  const approved = record.is_approved as boolean | undefined;
  const votes = record.votes as Record<string, string> | undefined;
  const rationale = (record.rationale || record.decision_rationale) as string | undefined;
  const flags = record.condition_flags as string[] | undefined;

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <div>
        <div className="mb-2">
          {approved === true ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-green-500/10 px-3 py-1 text-sm font-medium text-green-400">
              <CheckCircle2 className="h-3.5 w-3.5" />
              IC Approved
            </span>
          ) : approved === false ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-red-500/10 px-3 py-1 text-sm font-medium text-red-400">
              <XCircle className="h-3.5 w-3.5" />
              Not Approved
            </span>
          ) : null}
        </div>
        {votes != null && (
          <div className="space-y-1">
            {Object.entries(votes).map(([member, vote]) => {
              const vStr = String(vote).toLowerCase();
              const pass = ["approve", "yes", "pass"].includes(vStr);
              return (
                <p key={member} className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
                  {pass ? (
                    <CheckCircle2 className="h-3 w-3 text-green-400" />
                  ) : (
                    <XCircle className="h-3 w-3 text-red-400" />
                  )}
                  {member}: <span className="text-[var(--text-secondary)]">{vote}</span>
                </p>
              );
            })}
          </div>
        )}
      </div>
      <div>
        {rationale && (
          <p className="text-xs italic text-[var(--text-secondary)]">{rationale.slice(0, 400)}</p>
        )}
        {flags && flags.length > 0 && (
          <p className="mt-2 text-xs text-[var(--text-muted)]">
            Condition flags: {flags.join(", ")}
          </p>
        )}
      </div>
    </div>
  );
}

function MandateCompliance({ mandate }: { mandate: Record<string, unknown> }) {
  const compliant = mandate.is_compliant as boolean | undefined;
  const violations = (mandate.violations || []) as Array<Record<string, unknown> | string>;
  return (
    <div>
      {compliant === true ? (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-green-500/10 px-3 py-1 text-sm font-medium text-green-400">
          <CheckCircle2 className="h-3.5 w-3.5" />
          All mandate constraints passed
        </span>
      ) : (
        <div>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-yellow-500/10 px-3 py-1 text-sm font-medium text-yellow-400">
            <AlertTriangle className="h-3.5 w-3.5" />
            Mandate violations detected
          </span>
          {violations.length > 0 && (
            <ul className="mt-3 space-y-1">
              {violations.map((v, i) => (
                <li key={i} className="text-xs text-[var(--text-muted)]">
                  •{" "}
                  {typeof v === "object"
                    ? String((v as Record<string, unknown>).description ?? JSON.stringify(v))
                    : String(v)}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

function EsgPanel({ scores }: { scores: Array<Record<string, unknown>> }) {
  const compositeScores = scores
    .map((s) => Number(s.esg_score ?? 0))
    .filter((n) => n > 0);
  const exclusions = scores.filter((s) => s.exclusion_trigger).map((s) => String(s.ticker));
  const avg = compositeScores.length
    ? compositeScores.reduce((a, b) => a + b, 0) / compositeScores.length
    : 0;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-4">
        <MetricCard label="Portfolio ESG Avg" value={`${avg.toFixed(0)} / 100`} icon={<Leaf className="h-4 w-4" />} />
        <MetricCard label="Tickers Scored" value={scores.length} />
        <MetricCard label="Exclusion Triggers" value={exclusions.length} subtext={exclusions.join(", ") || "None"} />
      </div>
      {exclusions.length > 0 && (
        <div className="rounded-lg border border-yellow-500/20 bg-yellow-500/5 px-4 py-2">
          <p className="text-xs text-yellow-400">⚡ Exclusion triggered for: {exclusions.join(", ")}</p>
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-[var(--border)]">
              {["Ticker", "ESG", "E", "S", "G", "Exclusion", "Top Controversy"].map((h) => (
                <th key={h} className="px-3 py-2 text-left font-medium text-[var(--text-muted)]">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border)]">
            {scores.map((s, i) => {
              const flags = (s.controversy_flags as string[] | undefined) || [];
              return (
                <tr key={i} className="hover:bg-[var(--surface-2)]">
                  <td className="px-3 py-2 font-mono font-medium text-[var(--text-primary)]">{String(s.ticker ?? "—")}</td>
                  <td className="px-3 py-2 tabular-nums text-[var(--text-secondary)]">{String(s.esg_score ?? "—")}</td>
                  <td className="px-3 py-2 tabular-nums text-[var(--text-secondary)]">{String(s.e_score ?? "—")}</td>
                  <td className="px-3 py-2 tabular-nums text-[var(--text-secondary)]">{String(s.s_score ?? "—")}</td>
                  <td className="px-3 py-2 tabular-nums text-[var(--text-secondary)]">{String(s.g_score ?? "—")}</td>
                  <td className="px-3 py-2">
                    {s.exclusion_trigger ? (
                      <span className="text-red-400">Triggered</span>
                    ) : (
                      <span className="text-green-400">Clear</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-[var(--text-muted)]">{flags.slice(0, 2).join("; ") || "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function OptimisationPanel({
  optResults,
  baselineWeights,
}: {
  optResults: Record<string, unknown>;
  baselineWeights: Record<string, number>;
}) {
  const rp = (optResults.risk_parity || {}) as Record<string, unknown>;
  const mv = (optResults.min_variance || {}) as Record<string, unknown>;
  const ms = (optResults.max_sharpe || {}) as Record<string, unknown>;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {Object.keys(rp).length > 0 && (
          <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-4">
            <p className="mb-2 text-xs font-semibold text-[var(--text-secondary)]">Risk Parity</p>
            <p className="text-xs text-[var(--text-muted)]">Expected Vol: <span className="text-[var(--text-secondary)]">{Number(rp.expected_volatility_pct ?? 0).toFixed(1)}%</span></p>
            <p className="text-xs text-[var(--text-muted)]">Expected Ret: <span className="text-[var(--text-secondary)]">{Number(rp.expected_return_pct ?? 0).toFixed(1)}%</span></p>
          </div>
        )}
        {Object.keys(mv).length > 0 && (
          <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-4">
            <p className="mb-2 text-xs font-semibold text-[var(--text-secondary)]">Min Variance</p>
            <p className="text-xs text-[var(--text-muted)]">Expected Vol: <span className="text-[var(--text-secondary)]">{Number(mv.expected_volatility_pct ?? 0).toFixed(1)}%</span></p>
            <p className="text-xs text-[var(--text-muted)]">Sharpe: <span className="text-[var(--text-secondary)]">{Number(mv.sharpe_ratio ?? 0).toFixed(2)}</span></p>
          </div>
        )}
        {Object.keys(ms).length > 0 && (
          <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-4">
            <p className="mb-2 text-xs font-semibold text-[var(--text-secondary)]">Max Sharpe</p>
            <p className="text-xs text-[var(--text-muted)]">Sharpe: <span className="text-[var(--text-secondary)]">{Number(ms.sharpe_ratio ?? 0).toFixed(2)}</span></p>
            <p className="text-xs text-[var(--text-muted)]">Expected Ret: <span className="text-[var(--text-secondary)]">{Number(ms.expected_return_pct ?? 0).toFixed(1)}%</span></p>
          </div>
        )}
      </div>
      {Object.keys(rp.weights || {}).length > 0 && (
        <details className="rounded-lg border border-[var(--border)]">
          <summary className="cursor-pointer px-4 py-2 text-xs font-medium text-[var(--text-secondary)]">
            Risk Parity vs Baseline Weights
          </summary>
          <div className="overflow-x-auto p-3">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-[var(--border)]">
                  {["Ticker", "Baseline %", "Risk Parity %", "Active %"].map((h) => (
                    <th key={h} className="px-3 py-2 text-left font-medium text-[var(--text-muted)]">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {Object.entries(rp.weights as Record<string, number>)
                  .sort(([, a], [, b]) => b - a)
                  .map(([ticker, w]) => {
                    const bw = (baselineWeights[ticker] ?? 0) * 100;
                    return (
                      <tr key={ticker} className="hover:bg-[var(--surface-2)]">
                        <td className="px-3 py-2 font-mono text-[var(--text-primary)]">{ticker}</td>
                        <td className="px-3 py-2 tabular-nums text-[var(--text-secondary)]">{bw.toFixed(1)}%</td>
                        <td className="px-3 py-2 tabular-nums text-[var(--text-secondary)]">{w.toFixed(1)}%</td>
                        <td className={`px-3 py-2 tabular-nums ${(w - bw) >= 0 ? "text-green-400" : "text-red-400"}`}>
                          {((w - bw) >= 0 ? "+" : "")}{(w - bw).toFixed(1)}%
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        </details>
      )}
      <p className="text-xs text-[var(--text-muted)]">
        Optimisation uses synthetic return data — for structural illustration only.
      </p>
    </div>
  );
}

function RebalancePanel({ rebalData }: { rebalData: Record<string, unknown> }) {
  const trades = (rebalData.trades as Array<Record<string, unknown>>) || [];
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-4">
        <MetricCard label="Trades Required" value={rebalData.trade_count as number ?? trades.length} />
        <MetricCard label="Turnover" value={`${Number(rebalData.total_turnover_pct ?? 0).toFixed(1)}%`} />
        <MetricCard label="Est. Avg Impact" value={`${Number(rebalData.estimated_total_impact_bps ?? 0).toFixed(1)} bps`} />
      </div>
      {trades.length > 0 && (
        <details className="rounded-lg border border-[var(--border)]">
          <summary className="cursor-pointer px-4 py-2 text-xs font-medium text-[var(--text-secondary)]">
            Trade-Level Detail ({trades.length} trades)
          </summary>
          <div className="overflow-x-auto p-3">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-[var(--border)]">
                  {["Ticker", "Direction", "Current %", "Target %", "Delta %", "Impact bps"].map((h) => (
                    <th key={h} className="px-3 py-2 text-left font-medium text-[var(--text-muted)]">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {trades.map((t, i) => (
                  <tr key={i} className="hover:bg-[var(--surface-2)]">
                    <td className="px-3 py-2 font-mono text-[var(--text-primary)]">{String(t.ticker)}</td>
                    <td className={`px-3 py-2 font-medium ${String(t.direction).toUpperCase() === "BUY" ? "text-green-400" : "text-red-400"}`}>
                      {String(t.direction).toUpperCase()}
                    </td>
                    <td className="px-3 py-2 tabular-nums text-[var(--text-secondary)]">{Number(t.current_weight_pct ?? 0).toFixed(1)}%</td>
                    <td className="px-3 py-2 tabular-nums text-[var(--text-secondary)]">{Number(t.target_weight_pct ?? 0).toFixed(1)}%</td>
                    <td className={`px-3 py-2 tabular-nums ${Number(t.delta_weight_pct ?? 0) >= 0 ? "text-green-400" : "text-red-400"}`}>
                      {Number(t.delta_weight_pct ?? 0) >= 0 ? "+" : ""}{Number(t.delta_weight_pct ?? 0).toFixed(1)}%
                    </td>
                    <td className="px-3 py-2 tabular-nums text-[var(--text-muted)]">{Number(t.market_impact_bps ?? 0).toFixed(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
      {!!rebalData.summary && (
        <p className="text-xs text-[var(--text-muted)]">{String(rebalData.summary)}</p>
      )}
    </div>
  );
}

function AttributionPanel({ attribution }: { attribution: Record<string, unknown> }) {
  const sectorAlloc = (attribution.sector_allocation || {}) as Record<string, number>;
  const sectorSel = (attribution.sector_selection || {}) as Record<string, number>;
  const sectors = Object.keys(sectorAlloc);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <MetricCard
          label="Portfolio Return"
          value={`${Number(attribution.total_portfolio_return_pct ?? 0).toFixed(2)}%`}
          icon={<TrendingDown className="h-4 w-4" />}
        />
        <MetricCard
          label="Benchmark Return (SPY)"
          value={`${Number(attribution.total_benchmark_return_pct ?? 0).toFixed(2)}%`}
        />
        <MetricCard
          label="Excess Return"
          value={`${Number(attribution.excess_return_pct ?? 0).toFixed(2)}%`}
        />
        <MetricCard
          label="Allocation Effect"
          value={`${Number(attribution.allocation_effect_pct ?? 0).toFixed(3)}%`}
        />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <MetricCard
          label="Selection Effect"
          value={`${Number(attribution.selection_effect_pct ?? 0).toFixed(3)}%`}
        />
        <MetricCard
          label="Interaction Effect"
          value={`${Number(attribution.interaction_effect_pct ?? 0).toFixed(3)}%`}
        />
      </div>
      {sectors.length > 0 && (
        <details className="rounded-lg border border-[var(--border)]">
          <summary className="cursor-pointer px-4 py-2 text-xs font-medium text-[var(--text-secondary)]">
            Sector Attribution Detail
          </summary>
          <div className="overflow-x-auto p-3">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-[var(--border)]">
                  {["Sector", "Allocation Effect %", "Selection Effect %"].map((h) => (
                    <th key={h} className="px-3 py-2 text-left font-medium text-[var(--text-muted)]">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {sectors.sort().map((sector) => (
                  <tr key={sector} className="hover:bg-[var(--surface-2)]">
                    <td className="px-3 py-2 text-[var(--text-primary)]">{sector}</td>
                    <td className="px-3 py-2 tabular-nums text-[var(--text-secondary)]">
                      {(sectorAlloc[sector] || 0).toFixed(4)}
                    </td>
                    <td className="px-3 py-2 tabular-nums text-[var(--text-secondary)]">
                      {(sectorSel[sector] || 0).toFixed(4)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
      <p className="text-xs text-[var(--text-muted)]">
        Attribution uses live price data where available (yfinance), falling back to synthetic returns.
      </p>
    </div>
  );
}
