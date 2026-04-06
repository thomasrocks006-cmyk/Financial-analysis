"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { startRun } from "@/lib/api";
import { usePipelineStore } from "@/lib/store";
import { cn } from "@/lib/utils";

const PRESET_UNIVERSES = [
  { label: "AI COMPUTE",      tickers: ["NVDA", "TSM", "AMD", "INTC", "QCOM"] },
  { label: "AI INFRASTRUCTURE",tickers: ["NVDA", "TSM", "MSFT", "AMZN", "GOOGL"] },
  { label: "POWER & ENERGY",   tickers: ["NEE", "AES", "ETN", "VST", "CEG"] },
  { label: "ASX TECH",         tickers: ["WTC", "XRO", "CPU", "TNE", "ALU"] },
];

const MODELS = ["claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5-20251001"];

export default function NewRunPage() {
  const router    = useRouter();
  const store     = usePipelineStore();

  const [tickers,     setTickers]     = useState<string[]>(store.universe.length ? store.universe : []);
  const [tickerInput, setTickerInput] = useState("");
  const [model,       setModel]       = useState(store.model || "claude-sonnet-4-6");
  const [market,      setMarket]      = useState<"us"|"au"|"global"|"mixed">(store.market || "au");
  const [runLabel,    setRunLabel]    = useState("");
  const [loading,     setLoading]     = useState(false);
  const [error,       setError]       = useState<string | null>(null);

  const addTicker = (raw: string) => {
    const t = raw.trim().toUpperCase();
    if (t && !tickers.includes(t)) setTickers((prev) => [...prev, t]);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addTicker(tickerInput);
      setTickerInput("");
    }
  };

  const handleSubmit = async () => {
    if (tickers.length === 0) { setError("ADD AT LEAST ONE TICKER"); return; }
    setLoading(true);
    setError(null);
    try {
      const result = await startRun({
        universe:  tickers,
        llm_model: model,
        market,
        run_label: runLabel || undefined,
      });
      router.push(`/runs/${result.run_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message.toUpperCase() : "PIPELINE START FAILED");
      setLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-2xl">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-[var(--accent)] text-sm tracking-[.15em]">
          CONFIGURE PIPELINE RUN
        </h1>
        <p className="text-[var(--text-muted)] text-[10px] tracking-[.08em] mt-1">
          15-STAGE AI RESEARCH PIPELINE — AU MARKET
        </p>
      </div>

      <div className="space-y-5">

        {/* Ticker universe */}
        <div>
          <label className="block text-[var(--text-label)] text-[10px] tracking-[.1em] mb-2">
            TICKER UNIVERSE
          </label>
          <div className="flex gap-2 mb-3">
            <input
              value={tickerInput}
              onChange={(e) => setTickerInput(e.target.value.toUpperCase())}
              onKeyDown={handleKeyDown}
              placeholder="ENTER TICKER + ENTER"
              maxLength={6}
              className="bg-[var(--surface-2)] border border-[var(--border)] px-3 py-2 text-[var(--text-label)] text-[12px] outline-none focus:border-[var(--accent)] w-44 placeholder:text-[var(--text-muted)] placeholder:text-[10px]"
            />
            <button
              onClick={() => { addTicker(tickerInput); setTickerInput(""); }}
              className="px-4 py-2 border border-[var(--border)] text-[var(--text-secondary)] text-[10px] tracking-[.08em] hover:border-[var(--accent)] hover:text-[var(--accent)] transition-colors"
            >
              ADD
            </button>
          </div>

          {/* Preset universes */}
          <div className="flex flex-wrap gap-2 mb-3">
            {PRESET_UNIVERSES.map(({ label, tickers: t }) => (
              <button
                key={label}
                onClick={() => setTickers(t)}
                className="text-[9px] tracking-[.06em] px-2 py-1 border border-[var(--border-2)] text-[var(--text-muted)] hover:border-[var(--accent)] hover:text-[var(--accent)] transition-colors"
              >
                {label}
              </button>
            ))}
          </div>

          {/* Added tickers */}
          {tickers.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {tickers.map((t) => (
                <span
                  key={t}
                  onClick={() => setTickers((prev) => prev.filter((x) => x !== t))}
                  className="px-3 py-1 bg-[var(--accent-faint)] border border-[var(--accent)] text-[var(--accent)] text-[11px] cursor-pointer hover:bg-[var(--error-faint)] hover:border-[var(--error)] hover:text-[var(--error)] transition-colors"
                >
                  {t} ×
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Model */}
        <div className="border-t border-[var(--border-2)] pt-5">
          <label className="block text-[var(--text-label)] text-[10px] tracking-[.1em] mb-2">
            MODEL
          </label>
          <div className="flex gap-2 flex-wrap">
            {MODELS.map((m) => (
              <button
                key={m}
                onClick={() => setModel(m)}
                className={cn(
                  "text-[10px] tracking-[.04em] px-3 py-1.5 border transition-colors",
                  model === m
                    ? "border-[var(--accent)] bg-[var(--accent-faint)] text-[var(--accent)]"
                    : "border-[var(--border)] text-[var(--text-muted)] hover:border-[var(--text-secondary)]"
                )}
              >
                {m}
              </button>
            ))}
          </div>
        </div>

        {/* Market */}
        <div className="border-t border-[var(--border-2)] pt-5">
          <label className="block text-[var(--text-label)] text-[10px] tracking-[.1em] mb-2">
            MARKET
          </label>
          <div className="flex gap-2">
            {(["au", "us", "global", "mixed"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMarket(m)}
                className={cn(
                  "text-[10px] tracking-[.06em] px-3 py-1.5 border transition-colors",
                  market === m
                    ? "border-[var(--accent)] bg-[var(--accent-faint)] text-[var(--accent)]"
                    : "border-[var(--border)] text-[var(--text-muted)] hover:border-[var(--text-secondary)]"
                )}
              >
                {m.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        {/* Run label */}
        <div className="border-t border-[var(--border-2)] pt-5">
          <label className="block text-[var(--text-label)] text-[10px] tracking-[.1em] mb-2">
            RUN LABEL (OPTIONAL)
          </label>
          <input
            value={runLabel}
            onChange={(e) => setRunLabel(e.target.value)}
            placeholder="e.g. AI INFRA Q2 2026"
            className="bg-[var(--surface-2)] border border-[var(--border)] px-3 py-2 text-[var(--text-primary)] text-[12px] outline-none focus:border-[var(--accent)] w-full placeholder:text-[var(--text-muted)] placeholder:text-[10px]"
          />
        </div>

        {/* Error */}
        {error && (
          <div className="border border-[var(--error)] bg-[var(--error-faint)] px-4 py-2 text-[var(--error)] text-[11px] tracking-[.06em]">
            ERROR: {error}
          </div>
        )}

        {/* Submit */}
        <div className="border-t border-[var(--border-2)] pt-5 flex gap-3">
          <button
            onClick={handleSubmit}
            disabled={loading}
            className="px-6 py-2.5 bg-[var(--accent)] text-black text-[11px] tracking-[.12em] hover:bg-[var(--accent-hover)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? "INITIATING..." : "INITIATE PIPELINE  [GO]"}
          </button>
          <button
            onClick={() => router.back()}
            className="px-4 py-2.5 border border-[var(--border)] text-[var(--text-muted)] text-[11px] tracking-[.08em] hover:border-[var(--text-secondary)] transition-colors"
          >
            CANCEL
          </button>
        </div>
      </div>
    </div>
  );
}
