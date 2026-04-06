"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { usePipelineStore } from "@/lib/store";
import type { UniverseMode } from "@/lib/store";
import {
  startRun,
  getUniversePresets,
  getUniverseTickers,
  type UniversePreset,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { Layers, Globe, Cpu, DollarSign, Heart, Zap, BarChart2, Leaf, Building2, Package, Shuffle, ChevronRight } from "lucide-react";

const UNIVERSE_ICONS: Record<string, React.ReactNode> = {
  broad_market:    <Globe className="h-4 w-4" />,
  ai_infrastructure: <Cpu className="h-4 w-4" />,
  global_tech:     <Layers className="h-4 w-4" />,
  healthcare:      <Heart className="h-4 w-4" />,
  financials:      <DollarSign className="h-4 w-4" />,
  consumer:        <Package className="h-4 w-4" />,
  energy_materials:<Zap className="h-4 w-4" />,
  real_estate:     <Building2 className="h-4 w-4" />,
  fixed_income:    <BarChart2 className="h-4 w-4" />,
  commodities:     <Leaf className="h-4 w-4" />,
  alternatives:    <Shuffle className="h-4 w-4" />,
  etf_benchmarks:  <BarChart2 className="h-4 w-4" />,
};

const MODE_OPTIONS: Array<{ id: UniverseMode; label: string; detail: string }> = [
  {
    id: "discovery",
    label: "Broad Discovery (Recommended)",
    detail:
      "Start from a full cross-asset universe spanning equities, ETFs, fixed income, commodities, and alternatives. The pipeline ranks and filters candidates via live research to produce a high-conviction shortlist.",
  },
  {
    id: "preset",
    label: "Named Preset",
    detail:
      "Select a pre-defined thematic universe (AI Infrastructure, Healthcare, Fixed Income, etc.). The pipeline researches the preset list and produces a focused report.",
  },
  {
    id: "custom",
    label: "Custom Basket",
    detail:
      "Enter your own comma-separated ticker list. Useful for ad-hoc screens or single-ticker deep-dives.",
  },
];

export default function NewRunPage() {
  const router = useRouter();
  const store = usePipelineStore();

  const [universeMode, setUniverseMode] = useState<UniverseMode>(store.universeMode);
  const [selectedPreset, setSelectedPreset] = useState<string>(store.universePreset || "broad_market");
  const [customTickers, setCustomTickers] = useState<string>(
    store.universeMode === "custom" ? store.universe.join(", ") : ""
  );
  const [launching, setLaunching] = useState(false);
  const [launchError, setLaunchError] = useState<string | null>(null);

  const { data: presetsData } = useQuery({
    queryKey: ["universe-presets"],
    queryFn: getUniversePresets,
    staleTime: 60_000,
  });

  const { data: presetTickersData } = useQuery({
    queryKey: ["universe-tickers", selectedPreset],
    queryFn: () => getUniverseTickers(selectedPreset),
    enabled: universeMode === "preset" && !!selectedPreset,
    staleTime: 60_000,
  });

  const presets: UniversePreset[] = presetsData?.universes ?? [];

  function getEffectiveUniverse(): string[] {
    if (universeMode === "custom") {
      return customTickers
        .split(/[\s,]+/)
        .map((t) => t.trim().toUpperCase())
        .filter(Boolean);
    }
    if (universeMode === "preset" && presetTickersData?.tickers) {
      return presetTickersData.tickers;
    }
    // discovery — use broad market from store
    return store.universe;
  }

  async function handleLaunch() {
    setLaunchError(null);
    const tickers = getEffectiveUniverse();
    if (!tickers.length) {
      setLaunchError("Please add at least one ticker.");
      return;
    }

    // Persist mode & preset to store
    store.setUniverseMode(universeMode);
    store.setUniversePreset(selectedPreset);
    if (universeMode === "custom") store.setUniverse(tickers);

    setLaunching(true);
    try {
      const result = await startRun({
        universe: tickers,
        universe_mode: universeMode,
        run_label: store.runLabel || undefined,
        llm_model: store.model,
        llm_temperature: store.temperature,
        max_positions: store.maxPositions,
        benchmark_ticker: store.benchmarkTicker,
        portfolio_variants: store.portfolioVariants,
        market: store.market,
        client_profile: store.clientProfile,
      });
      store.setRunStarted(result.run_id);
      router.push(`/runs/${result.run_id}`);
    } catch (err) {
      setLaunchError(err instanceof Error ? err.message : "Failed to start run.");
      setLaunching(false);
    }
  }

  const effectiveTickers = getEffectiveUniverse();

  return (
    <div className="mx-auto max-w-5xl space-y-0 divide-y divide-[var(--border)]">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3">
        <div>
          <span className="text-[var(--text-label)] text-[9px] tracking-[.12em] uppercase">
            Meridian Research Terminal
          </span>
          <div className="mt-1 text-[10px] tracking-[.08em] text-[var(--text-muted)] uppercase">
            New Research Run — Universe Selector
          </div>
        </div>
        <button
          onClick={handleLaunch}
          disabled={launching || !effectiveTickers.length}
          className={cn(
            "border px-4 py-2 text-[11px] tracking-[.08em] uppercase transition-colors",
            launching || !effectiveTickers.length
              ? "border-[var(--border)] text-[var(--text-muted)] cursor-not-allowed"
              : "border-[var(--accent)] text-[var(--accent)] hover:bg-[var(--accent)] hover:text-black"
          )}
        >
          {launching ? "LAUNCHING…" : `LAUNCH [${effectiveTickers.length} TICKERS]`}
        </button>
      </div>

      {launchError && (
        <div className="border-y border-[var(--error)] bg-[var(--error-faint)] px-4 py-3 text-[11px] text-[var(--error)]">
          {launchError}
        </div>
      )}

      {/* Mode selector */}
      <div className="bg-[var(--surface)]">
        <div className="px-4 py-1.5 bg-[var(--surface-2)]">
          <span className="text-[var(--text-label)] text-[9px] tracking-[.1em] uppercase">
            Research Mode
          </span>
        </div>
        <div className="grid md:grid-cols-3 divide-x divide-[var(--border)]">
          {MODE_OPTIONS.map((opt) => (
            <button
              key={opt.id}
              onClick={() => setUniverseMode(opt.id)}
              className={cn(
                "text-left px-4 py-4 transition-colors",
                universeMode === opt.id
                  ? "bg-[var(--accent-faint)]"
                  : "hover:bg-[var(--surface-2)]"
              )}
            >
              <div className={cn(
                "text-[10px] tracking-[.08em] uppercase font-medium",
                universeMode === opt.id ? "text-[var(--accent)]" : "text-[var(--text-secondary)]"
              )}>
                {universeMode === opt.id && "▶ "}{opt.label}
              </div>
              <div className="mt-2 text-[11px] text-[var(--text-muted)] leading-relaxed">
                {opt.detail}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Discovery mode — show broad universe breakdown */}
      {universeMode === "discovery" && (
        <div className="bg-[var(--surface)]">
          <div className="px-4 py-1.5 bg-[var(--surface-2)]">
            <span className="text-[var(--text-label)] text-[9px] tracking-[.1em] uppercase">
              Broad Market Universe — {effectiveTickers.length} tickers across all asset classes
            </span>
          </div>
          <div className="px-4 py-3 space-y-3 text-[11px]">
            <div className="text-[var(--text-secondary)] leading-relaxed">
              The pipeline begins with this full cross-asset universe and uses live news, fundamentals,
              and AI research to narrow it down to a high-conviction shortlist.  No pre-selection is made —
              every asset class competes on merit.
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {[
                { label: "Tech, AI & Semiconductors", tags: "AAPL · NVDA · MSFT · ARM · TSM · ANET…" },
                { label: "Healthcare & Pharma", tags: "LLY · UNH · JNJ · ABBV · MRK…" },
                { label: "Financials & Fintech", tags: "JPM · BAC · GS · V · MA · BLK…" },
                { label: "Consumer (Staples & Disc.)", tags: "TSLA · WMT · COST · HD · MCD…" },
                { label: "Energy, Materials & Industrials", tags: "XOM · CVX · NEE · CAT · HON · BA…" },
                { label: "Real Estate / REITs", tags: "EQIX · DLR · AMT · PLD · O…" },
                { label: "International Equities", tags: "SAP · AZN · ASML · TM · BABA…" },
                { label: "ETFs (Sector & Benchmark)", tags: "SPY · QQQ · IWM · XLK · XLV · SOXX…" },
                { label: "Fixed Income ETFs", tags: "TLT · IEF · LQD · HYG · TIP · AGG…" },
                { label: "Commodities", tags: "GLD · SLV · USO · DBA · PDBC…" },
                { label: "Alternatives", tags: "IBIT · FBTC · DBMF · KMLM · VNQ…" },
              ].map((row) => (
                <div key={row.label} className="border border-[var(--border)] px-3 py-2">
                  <div className="text-[10px] text-[var(--text-secondary)]">{row.label}</div>
                  <div className="mt-1 text-[9px] text-[var(--text-muted)] font-mono truncate">{row.tags}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Preset mode — universe picker */}
      {universeMode === "preset" && (
        <div className="bg-[var(--surface)]">
          <div className="px-4 py-1.5 bg-[var(--surface-2)]">
            <span className="text-[var(--text-label)] text-[9px] tracking-[.1em] uppercase">
              Select a Universe Preset
            </span>
          </div>
          {presets.length === 0 ? (
            <div className="px-4 py-4 text-[11px] text-[var(--text-muted)]">
              Loading presets… (requires backend API to be running)
            </div>
          ) : (
            <div className="grid md:grid-cols-2 xl:grid-cols-3">
              {presets.map((preset) => (
                <button
                  key={preset.id}
                  onClick={() => setSelectedPreset(preset.id)}
                  className={cn(
                    "text-left border border-[var(--border)] px-4 py-4 transition-colors",
                    selectedPreset === preset.id
                      ? "bg-[var(--accent-faint)] border-[var(--accent)]"
                      : "hover:bg-[var(--surface-2)]"
                  )}
                >
                  <div className="flex items-center gap-2">
                    <span className={selectedPreset === preset.id ? "text-[var(--accent)]" : "text-[var(--text-muted)]"}>
                      {UNIVERSE_ICONS[preset.id] ?? <Layers className="h-4 w-4" />}
                    </span>
                    <span className={cn(
                      "text-[10px] tracking-[.08em] uppercase font-medium",
                      selectedPreset === preset.id ? "text-[var(--accent)]" : "text-[var(--text-secondary)]"
                    )}>
                      {preset.label}
                    </span>
                    <span className="ml-auto text-[10px] tabular-nums text-[var(--text-muted)]">
                      {preset.ticker_count}
                    </span>
                  </div>
                  <div className="mt-2 text-[11px] text-[var(--text-muted)] leading-relaxed line-clamp-2">
                    {preset.description}
                  </div>
                  <div className="mt-1 text-[9px] text-[var(--info)] uppercase tracking-[.06em]">
                    {preset.asset_classes}
                  </div>
                </button>
              ))}
            </div>
          )}

          {/* Preview selected preset tickers */}
          {selectedPreset && presetTickersData && (
            <div className="px-4 py-3 border-t border-[var(--border)]">
              <div className="text-[9px] tracking-[.1em] text-[var(--text-label)] uppercase mb-2">
                {presetTickersData.count} tickers in "{selectedPreset}"
              </div>
              <div className="flex flex-wrap gap-1">
                {presetTickersData.tickers.slice(0, 60).map((t) => (
                  <span key={t} className="border border-[var(--border)] px-1.5 py-0.5 text-[9px] text-[var(--text-secondary)] font-mono">
                    {t}
                  </span>
                ))}
                {presetTickersData.tickers.length > 60 && (
                  <span className="text-[10px] text-[var(--text-muted)]">
                    +{presetTickersData.tickers.length - 60} more
                  </span>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Custom mode — ticker input */}
      {universeMode === "custom" && (
        <div className="bg-[var(--surface)]">
          <div className="px-4 py-1.5 bg-[var(--surface-2)]">
            <span className="text-[var(--text-label)] text-[9px] tracking-[.1em] uppercase">
              Custom Ticker Basket
            </span>
          </div>
          <div className="px-4 py-4 space-y-3">
            <div className="text-[11px] text-[var(--text-secondary)]">
              Enter comma or space-separated ticker symbols.  Supports equities (AAPL),
              ETFs (SPY), indices (^GSPC), and ASX tickers (BHP.AX).
            </div>
            <textarea
              value={customTickers}
              onChange={(e) => setCustomTickers(e.target.value)}
              placeholder="AAPL, MSFT, NVDA, SPY, TLT, GLD…"
              rows={4}
              className="w-full border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-[11px] text-[var(--text-primary)] font-mono resize-none focus:outline-none focus:border-[var(--accent)]"
            />
            <div className="text-[10px] text-[var(--text-muted)]">
              {getEffectiveUniverse().length} ticker(s) parsed
            </div>
          </div>
        </div>
      )}

      {/* Run configuration summary */}
      <div className="bg-[var(--surface)]">
        <div className="px-4 py-1.5 bg-[var(--surface-2)]">
          <span className="text-[var(--text-label)] text-[9px] tracking-[.1em] uppercase">
            Run Configuration
          </span>
        </div>
        <div className="grid md:grid-cols-2 xl:grid-cols-4 divide-x divide-[var(--border)]">
          {[
            ["Model", store.orchestrationMode === "auto" ? "MERIDIAN AUTO" : store.model.toUpperCase()],
            ["Market", store.market.toUpperCase()],
            ["Benchmark", store.benchmarkTicker],
            ["Max Positions", String(store.maxPositions)],
          ].map(([label, value]) => (
            <div key={label} className="px-4 py-3">
              <div className="text-[9px] tracking-[.1em] text-[var(--text-label)] uppercase">{label}</div>
              <div className="mt-1 text-[11px] text-[var(--text-primary)]">{value}</div>
            </div>
          ))}
        </div>
        <div className="px-4 py-3 border-t border-[var(--border)] text-[11px] text-[var(--text-muted)]">
          Change model, benchmark, and position limits in{" "}
          <a href="/settings" className="text-[var(--accent)] hover:underline">Settings</a>.
        </div>
      </div>

      {/* Launch bar */}
      <div className="bg-[var(--surface)] px-4 py-4 flex items-center justify-between gap-4">
        <div className="text-[11px] text-[var(--text-secondary)]">
          {universeMode === "discovery" && (
            <span>Broad Discovery — {effectiveTickers.length} tickers, live AI research will narrow to a high-conviction shortlist</span>
          )}
          {universeMode === "preset" && (
            <span>Preset: <span className="text-[var(--accent)]">{selectedPreset}</span> — {effectiveTickers.length} tickers</span>
          )}
          {universeMode === "custom" && (
            <span>Custom basket — {effectiveTickers.length} tickers</span>
          )}
        </div>
        <button
          onClick={handleLaunch}
          disabled={launching || !effectiveTickers.length}
          className={cn(
            "flex items-center gap-2 border px-6 py-2 text-[11px] tracking-[.08em] uppercase transition-colors",
            launching || !effectiveTickers.length
              ? "border-[var(--border)] text-[var(--text-muted)] cursor-not-allowed"
              : "border-[var(--accent)] text-[var(--accent)] hover:bg-[var(--accent)] hover:text-black"
          )}
        >
          {launching ? "LAUNCHING…" : "LAUNCH PIPELINE"}
          <ChevronRight className="h-3 w-3" />
        </button>
      </div>
    </div>
  );
}
