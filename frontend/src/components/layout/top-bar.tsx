"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { usePipelineStore } from "@/lib/store";
import { cn } from "@/lib/utils";

const ROUTE_MAP: Record<string, string> = {
  DASHBOARD:  "/",
  MONITOR:    "/monitor",
  PORTFOLIO:  "/portfolio",
  "NEW RUN":  "/runs/new",
  "NEW":      "/runs/new",
  RUNS:       "/runs",
  ACTIVE:     "/runs",
  SAVED:      "/saved",
  SETTINGS:   "/settings",
  REPORT:     "/saved",
  AUDIT:      "/audit",
  QUANT:      "/quant",
};

const MKT_DATA = [
  { sym: "SPX",    val: "5421.8", chg: "+12.4",   dir: 1 },
  { sym: "NDX",    val: "19284",  chg: "+89.2",   dir: 1 },
  { sym: "ASX200", val: "7892.1", chg: "-18.3",   dir: -1 },
  { sym: "NVDA",   val: "892.40", chg: "+21.0",   dir: 1 },
  { sym: "TSM",    val: "164.20", chg: "+1.30",   dir: 1 },
  { sym: "VIX",    val: "18.42",  chg: "+0.84",   dir: -1 },
  { sym: "AUD/USD",val: "0.6412", chg: "-0.0021", dir: -1 },
  { sym: "10Y",    val: "4.342",  chg: "+0.021",  dir: -1 },
];

export function TopBar() {
  const router = useRouter();
  const { activeRunId, runStatus, stages } = usePipelineStore();
  const completedCount  = stages.filter((s) => s.status === "completed").length;
  const runningStage    = stages.find((s) => s.status === "running");

  const [cmd,    setCmd]    = useState("");
  const [time,   setTime]   = useState("");
  const [mktIdx, setMktIdx] = useState(0);

  useEffect(() => {
    const tick = setInterval(() => {
      setTime(new Date().toLocaleTimeString("en-AU", {
        hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit",
      }));
      setMktIdx((i) => (i + 1) % MKT_DATA.length);
    }, 1000);
    setTime(new Date().toLocaleTimeString("en-AU", {
      hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit",
    }));
    return () => clearInterval(tick);
  }, []);

  const handleCmd = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key !== "Enter") return;
    const upper = cmd.trim().toUpperCase();
    const route = ROUTE_MAP[upper];
    if (route) router.push(route);
    setCmd("");
  };

  const mkt = MKT_DATA[mktIdx];

  return (
    <header className="flex-shrink-0 border-b-2 border-[var(--accent)] bg-[var(--surface)]">
      <div className="flex items-center gap-3 px-4 py-1.5">
        <span className="text-[var(--accent)] text-sm">{">"}</span>
        <input
          value={cmd}
          onChange={(e) => setCmd(e.target.value.toUpperCase())}
          onKeyDown={handleCmd}
          placeholder="COMMAND — TYPE SCREEN NAME + ENTER  (MONITOR  PORTFOLIO  AUDIT  QUANT  NEW RUN)"
          className="flex-1 bg-transparent border-none outline-none text-[var(--text-label)] text-[11px] tracking-[.04em] placeholder:text-[var(--text-muted)] placeholder:text-[10px]"
        />

        {activeRunId ? (
          <div className="flex items-center gap-3 text-[10px] shrink-0">
            <span className="text-[var(--text-muted)] tracking-[.06em]">
              RUN:{" "}
              <span className="text-[var(--accent)]">{activeRunId.slice(0, 20)}</span>
            </span>
            <span className="text-[var(--border)]">|</span>
            <span
              className={cn(
                "tracking-[.08em]",
                runStatus === "running"   && "text-[var(--accent)]",
                runStatus === "completed" && "text-[var(--success)]",
                runStatus === "failed"    && "text-[var(--error)]",
              )}
            >
              <span className={cn("inline-block mr-1", runStatus === "running" && "stage-running")}>
                {runStatus === "running" ? "●" : runStatus === "completed" ? "✓" : "✗"}
              </span>
              {runStatus?.toUpperCase()}
              {runningStage && ` S${String(completedCount).padStart(2, "0")}/15`}
            </span>
            {runningStage && (
              <>
                <span className="text-[var(--border)]">|</span>
                <span className="text-[var(--accent)] tracking-[.04em]">
                  {runningStage.label.toUpperCase()}
                </span>
              </>
            )}
          </div>
        ) : (
          <span className="text-[var(--text-muted)] text-[10px] tracking-[.06em] shrink-0">
            NO ACTIVE RUN
          </span>
        )}

        <span className="text-[var(--border)]">|</span>

        <div className="flex items-center gap-2 shrink-0">
          <span className="text-[var(--info)] text-[10px] tracking-[.04em]">{mkt.sym}</span>
          <span className="text-[var(--text-primary)] text-[10px]">{mkt.val}</span>
          <span className={cn("text-[10px]", mkt.dir > 0 ? "text-[var(--success)]" : "text-[var(--error)]")}>
            {mkt.chg}
          </span>
        </div>

        <span className="text-[var(--border)]">|</span>
        <span className="text-[var(--success)] text-[10px] shrink-0">{time} AEST</span>
      </div>
    </header>
  );
}
