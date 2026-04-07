"use client";

import { useEffect, useMemo, useState } from "react";
import { Globe, Settings as SettingsIcon, Server, SlidersHorizontal, Workflow } from "lucide-react";
import { usePipelineStore } from "@/lib/store";
import { getApiTargetLabel, getStoredApiBaseUrl, setStoredApiBaseUrl } from "@/lib/runtime-settings";
import { probeBackendConnection } from "@/lib/api";
import { cn } from "@/lib/utils";

export default function SettingsPage() {
  const store = usePipelineStore();
  const defaultApiUrl = process.env.NEXT_PUBLIC_API_URL || "";
  const [apiUrl, setApiUrl] = useState("");
  const [savedBanner, setSavedBanner] = useState<string | null>(null);
  const [connectionState, setConnectionState] = useState<"checking" | "online" | "offline">("checking");

  const runProbe = async () => {
    setConnectionState("checking");
    const { ok } = await probeBackendConnection();
    setConnectionState(ok ? "online" : "offline");
  };

  useEffect(() => {
    setApiUrl(getStoredApiBaseUrl() || defaultApiUrl);
  }, [defaultApiUrl]);

  useEffect(() => {
    let cancelled = false;
    probeBackendConnection().then(({ ok }) => {
      if (!cancelled) setConnectionState(ok ? "online" : "offline");
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const connectionLabel = useMemo(() => getApiTargetLabel(), [apiUrl]);

  const handleSaveApiUrl = () => {
    setStoredApiBaseUrl(apiUrl);
    setSavedBanner("Backend URL saved locally for this browser session profile.");
  };

  const handleResetApiUrl = () => {
    setStoredApiBaseUrl("");
    setApiUrl(defaultApiUrl);
    setSavedBanner("Backend URL reset to environment/default routing.");
  };

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <h1 className="text-xl font-bold text-[var(--text-primary)]">
        Settings
      </h1>

      {savedBanner && (
        <div className="border border-[var(--accent)] bg-[var(--accent-faint)] px-3 py-2 text-[11px] text-[var(--accent)]">
          {savedBanner}
        </div>
      )}

      {/* API Connection */}
      <div className="border border-[var(--border)] bg-[var(--surface)] p-4">
        <div className="flex items-center gap-2 mb-3">
          <Server className="h-4 w-4 text-[var(--accent)]" />
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">
            API Connection
          </h2>
        </div>
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-xs text-[var(--text-muted)]">
              Backend URL
            </label>
            <input
              type="text"
              value={apiUrl}
              onChange={(e) => setApiUrl(e.target.value)}
              placeholder="Leave blank to use the app's built-in API proxy"
              className="w-full border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-sm text-[var(--text-secondary)] font-mono"
            />
            <p className="mt-1 text-xs text-[var(--text-muted)]">
              Current target: {connectionLabel}
            </p>
            <p className="mt-1 text-xs text-[var(--text-muted)]">
              On remote/dev-container previews, a saved localhost URL can point at your own machine instead of this workspace. Leaving this blank is the safest default.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleSaveApiUrl}
              className="border border-[var(--accent)] px-3 py-1 text-[11px] tracking-[.06em] text-[var(--accent)] hover:bg-[var(--accent)] hover:text-black"
            >
              SAVE URL
            </button>
            <button
              onClick={handleResetApiUrl}
              className="border border-[var(--border)] px-3 py-1 text-[11px] tracking-[.06em] text-[var(--text-secondary)] hover:bg-[var(--surface-2)]"
            >
              RESET
            </button>
            <button
              onClick={runProbe}
              className="border border-[var(--border)] px-3 py-1 text-[11px] tracking-[.06em] text-[var(--text-secondary)] hover:bg-[var(--surface-2)]"
            >
              RETEST
            </button>
            <span
              className={cn(
                "border px-2 py-1 text-[10px] tracking-[.08em] uppercase",
                connectionState === "online" && "border-[var(--success)] text-[var(--success)] bg-[var(--success-faint)]",
                connectionState === "offline" && "border-[var(--error)] text-[var(--error)] bg-[var(--error-faint)]",
                connectionState === "checking" && "border-[var(--warning)] text-[var(--warning)]",
              )}
            >
              {connectionState === "online" ? "Backend online" : connectionState === "offline" ? "Backend offline" : "Checking"}
            </span>
          </div>
          <div className="border border-[var(--border)] bg-[var(--surface-2)] p-3 text-[11px] text-[var(--text-secondary)]">
            If you see <span className="text-[var(--error)]">Failed to fetch</span>, the usual cause is that the FastAPI API on port 8000 is not running yet. The frontend is up, but the data plane is offline.
          </div>
          <div className="grid gap-3 md:grid-cols-3 text-[11px] text-[var(--text-secondary)]">
            <div className="border border-[var(--border)] p-3">
              <div className="text-[10px] tracking-[.08em] uppercase text-[var(--text-label)]">Recommended local target</div>
              <div className="mt-2 font-mono text-[var(--text-primary)]">Blank / built-in proxy</div>
            </div>
            <div className="border border-[var(--border)] p-3">
              <div className="text-[10px] tracking-[.08em] uppercase text-[var(--text-label)]">Primary failure mode</div>
              <div className="mt-2">Backend not running or browser session saved an old URL.</div>
            </div>
            <div className="border border-[var(--border)] p-3">
              <div className="text-[10px] tracking-[.08em] uppercase text-[var(--text-label)]">Best operator flow</div>
              <div className="mt-2">Verify API → review defaults → launch from New Run.</div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <div className="border border-[var(--border)] bg-[var(--surface)] p-4">
          <div className="mb-3 flex items-center gap-2">
            <Workflow className="h-4 w-4 text-[var(--accent)]" />
            <h2 className="text-sm font-semibold text-[var(--text-primary)]">Model Orchestration</h2>
          </div>
          <div className="space-y-2 text-[11px] text-[var(--text-secondary)]">
            <button
              onClick={() => store.setOrchestrationMode("auto")}
              className={cn(
                "w-full border px-3 py-2 text-left",
                store.orchestrationMode === "auto"
                  ? "border-[var(--accent)] bg-[var(--accent-faint)] text-[var(--accent)]"
                  : "border-[var(--border)]",
              )}
            >
              <div className="text-[10px] tracking-[.08em] uppercase">Meridian Auto Routing</div>
              <div className="mt-1 text-[10px] text-[var(--text-muted)]">Default. The pipeline uses multiple models/APIs by stage.</div>
            </button>
            <button
              onClick={() => store.setOrchestrationMode("single")}
              className={cn(
                "w-full border px-3 py-2 text-left",
                store.orchestrationMode === "single"
                  ? "border-[var(--accent)] bg-[var(--accent-faint)] text-[var(--accent)]"
                  : "border-[var(--border)]",
              )}
            >
              <div className="text-[10px] tracking-[.08em] uppercase">Force Single Model</div>
              <div className="mt-1 text-[10px] text-[var(--text-muted)]">Use one explicit fallback model across the run.</div>
            </button>
            {store.orchestrationMode === "single" && (
              <select
                value={store.model}
                onChange={(e) => store.setModel(e.target.value)}
                className="w-full border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-[11px] text-[var(--text-primary)]"
              >
                {["claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5-20251001", "gpt-4o", "gpt-4o-mini", "gemini-1.5-pro"].map((model) => (
                  <option key={model} value={model}>{model}</option>
                ))}
              </select>
            )}
          </div>
        </div>

        <div className="border border-[var(--border)] bg-[var(--surface)] p-4">
          <div className="mb-3 flex items-center gap-2">
            <SlidersHorizontal className="h-4 w-4 text-[var(--accent)]" />
            <h2 className="text-sm font-semibold text-[var(--text-primary)]">Research Defaults</h2>
          </div>
          <div className="space-y-3 text-[11px] text-[var(--text-secondary)]">
            <div>
              <div className="mb-1 text-[10px] tracking-[.08em] text-[var(--text-label)] uppercase">Market</div>
              <div className="flex gap-1">
                {["us", "au", "global", "mixed"].map((market) => (
                  <button
                    key={market}
                    onClick={() => store.setMarket(market as "us" | "au" | "global" | "mixed")}
                    className={cn(
                      "flex-1 border py-1 text-[10px] uppercase",
                      store.market === market ? "border-[var(--accent)] text-[var(--accent)] bg-[var(--accent-faint)]" : "border-[var(--border)]",
                    )}
                  >
                    {market}
                  </button>
                ))}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <label className="block">
                <span className="mb-1 block text-[10px] tracking-[.08em] text-[var(--text-label)] uppercase">Benchmark</span>
                <input
                  value={store.benchmarkTicker}
                  onChange={(e) => store.setBenchmarkTicker(e.target.value.toUpperCase())}
                  className="w-full border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-[11px] text-[var(--text-primary)]"
                />
              </label>
              <label className="block">
                <span className="mb-1 block text-[10px] tracking-[.08em] text-[var(--text-label)] uppercase">Max Positions</span>
                <input
                  type="number"
                  min={1}
                  max={100}
                  value={store.maxPositions}
                  onChange={(e) => store.setMaxPositions(Number(e.target.value) || 1)}
                  className="w-full border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-[11px] text-[var(--text-primary)]"
                />
              </label>
            </div>
            <label className="block">
              <span className="mb-1 block text-[10px] tracking-[.08em] text-[var(--text-label)] uppercase">Default run label</span>
              <input
                value={store.runLabel}
                onChange={(e) => store.setRunLabel(e.target.value)}
                placeholder="E.G. JPAM AI INFRASTRUCTURE WATCHLIST"
                className="w-full border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-[11px] text-[var(--text-primary)]"
              />
            </label>
            <div>
              <div className="mb-1 text-[10px] tracking-[.08em] text-[var(--text-label)] uppercase">Default temperature: {store.temperature.toFixed(1)}</div>
              <input
                type="range"
                min={0}
                max={2}
                step={0.1}
                value={store.temperature}
                onChange={(e) => store.setTemperature(parseFloat(e.target.value))}
                className="w-full accent-[var(--accent)]"
              />
            </div>
            <div>
              <div className="mb-1 text-[10px] tracking-[.08em] text-[var(--text-label)] uppercase">Portfolio Variants</div>
              <div className="flex flex-wrap gap-1.5">
                {["balanced", "higher_return", "lower_volatility"].map((variant) => {
                  const active = store.portfolioVariants.includes(variant);
                  return (
                    <button
                      key={variant}
                      onClick={() => store.togglePortfolioVariant(variant)}
                      className={cn(
                        "border px-2 py-1 text-[10px] uppercase",
                        active ? "border-[var(--accent)] bg-[var(--accent-faint)] text-[var(--accent)]" : "border-[var(--border)]",
                      )}
                    >
                      {variant.replace(/_/g, " ")}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <div className="border border-[var(--border)] bg-[var(--surface)] p-4">
          <div className="mb-3 flex items-center gap-2">
            <Workflow className="h-4 w-4 text-[var(--accent)]" />
            <h2 className="text-sm font-semibold text-[var(--text-primary)]">Provider Routing Notes</h2>
          </div>
          <div className="space-y-2 text-[11px] text-[var(--text-secondary)]">
            {[
              ["Stage orchestration", "Meridian auto mode can route across multiple LLM/API calls by stage."],
              ["Single-model mode", "Only use when you explicitly want one fallback model across the run."],
              ["Data plane", "Market data, reports, audit packets, provenance, and quant panels come from the backend API."],
            ].map(([label, detail]) => (
              <div key={label} className="border border-[var(--border)] p-3">
                <div className="text-[10px] tracking-[.08em] uppercase text-[var(--text-label)]">{label}</div>
                <div className="mt-2">{detail}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="border border-[var(--border)] bg-[var(--surface)] p-4">
          <div className="mb-3 flex items-center gap-2">
            <Globe className="h-4 w-4 text-[var(--accent)]" />
            <h2 className="text-sm font-semibold text-[var(--text-primary)]">Desk Shortcuts</h2>
          </div>
          <div className="grid gap-2 text-[11px] text-[var(--text-secondary)]">
            {[
              ["DASHBOARD", "Front-door workspace with market pulse and quick actions"],
              ["NEW RUN", "Universe builder and launch controls"],
              ["RUNS", "Monitor active and recent orchestration"],
              ["SAVED", "Completed packets and retrieval"],
              ["SETTINGS", "Runtime URL and reusable defaults"],
            ].map(([label, detail]) => (
              <div key={label} className="flex items-start justify-between gap-3 border border-[var(--border)] px-3 py-2">
                <span className="text-[var(--accent)] text-[10px] tracking-[.08em] uppercase">{label}</span>
                <span className="text-right">{detail}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Surfaces */}
      <div className="border border-[var(--border)] bg-[var(--surface)] p-4">
        <div className="mb-3 flex items-center gap-2">
          <Globe className="h-4 w-4 text-[var(--accent)]" />
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">Operator Surfaces</h2>
        </div>
        <div className="grid gap-3 md:grid-cols-3 text-[11px]">
          <a href="http://localhost:3000" className="border border-[var(--border)] p-3 hover:border-[var(--accent)]">
            <div className="text-[10px] tracking-[.08em] text-[var(--text-label)] uppercase">Premium Frontend</div>
            <div className="mt-1 text-[var(--text-secondary)]">Primary operator workspace on port 3000.</div>
          </a>
          <a href="http://localhost:8501" className="border border-[var(--border)] p-3 hover:border-[var(--accent)]">
            <div className="text-[10px] tracking-[.08em] text-[var(--text-label)] uppercase">Streamlit Console</div>
            <div className="mt-1 text-[var(--text-secondary)]">Legacy operator console on port 8501.</div>
          </a>
          <a href="/runs/new" className="border border-[var(--border)] p-3 hover:border-[var(--accent)]">
            <div className="text-[10px] tracking-[.08em] text-[var(--text-label)] uppercase">Run Launcher</div>
            <div className="mt-1 text-[var(--text-secondary)]">Start a new pipeline with saved defaults.</div>
          </a>
        </div>
      </div>

      {/* About */}
      <div className="border border-[var(--border)] bg-[var(--surface)] p-4">
        <div className="flex items-center gap-2 mb-3">
          <SettingsIcon className="h-4 w-4 text-[var(--accent)]" />
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">
            About
          </h2>
        </div>
        <div className="space-y-2 text-sm text-[var(--text-secondary)]">
          <p>AI Infrastructure Research Platform — Premium Frontend</p>
          <p className="text-xs text-[var(--text-muted)]">
            Multi-asset Bloomberg-style Meridian terminal covering equities, ETFs, fixed income, commodities, and alternatives.
          </p>
          <p className="text-xs text-[var(--text-muted)]">
            15-stage pipeline with broad-market discovery mode, live market data, SSE pipeline tracking, report generation, audit quality scoring, provenance, and quant panels.
          </p>
          <p className="text-xs text-[var(--text-muted)]">
            This shell is Bloomberg-inspired, but it does not yet fully replicate the original multi-panel mockup. The biggest remaining gaps are deeper stage-detail views, richer report/audit operator screens, and more surface-level desk modules.
          </p>
        </div>
      </div>
    </div>
  );
}
