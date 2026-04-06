"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { usePipelineStore } from "@/lib/store";
import { STAGE_COUNT } from "@/lib/types";

const navItems = [
  { href: "/",          label: "DASHBOARD",    key: "F1" },
  { href: "/runs/new",  label: "NEW RUN",       key: "F9" },
  { href: "/runs",      label: "ACTIVE RUNS",   key: "F3" },
  { href: "/saved",     label: "SAVED REPORTS", key: "F4" },
  { href: "/settings",  label: "SETTINGS",      key: "F12" },
];

export function Sidebar() {
  const pathname     = usePathname();
  const { activeRunId, runStatus, stages, totalDurationMs } = usePipelineStore();
  const completedCount = stages.filter((s) => s.status === "completed").length;
  const progress       = (completedCount / STAGE_COUNT) * 100;
  const runningStage   = stages.find((s) => s.status === "running");

  return (
    <aside className="flex w-52 flex-col border-r border-[var(--border)] bg-[var(--surface)]">
      {/* Brand */}
      <div className="border-b border-[var(--border)] px-4 py-4">
        <div className="text-[var(--accent)] tracking-[.15em] text-sm font-normal">
          MERIDIAN
        </div>
        <div className="text-[var(--text-muted)] tracking-[.12em] text-[10px] mt-0.5">
          RESEARCH TERMINAL
        </div>
      </div>

      {/* Active run chip */}
      {activeRunId && (
        <div className="mx-2 mt-3 border border-[var(--accent)] bg-[var(--accent-faint)] px-3 py-2">
          <div className="flex items-center gap-2 mb-1.5">
            <span
              className={cn(
                "inline-block h-1.5 w-1.5 rounded-full bg-[var(--accent)]",
                runStatus === "running" && "stage-running"
              )}
            />
            <span className="text-[var(--accent)] text-[10px] tracking-[.08em]">
              {runStatus?.toUpperCase() ?? "IDLE"}
            </span>
          </div>
          {/* Progress bar */}
          <div className="h-px w-full bg-[var(--border-2)] mb-1">
            <div
              className="h-full bg-[var(--accent)] transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="text-[var(--text-muted)] text-[9px] tracking-[.06em]">
            S{String(completedCount).padStart(2, "0")}/{STAGE_COUNT}
            {runningStage ? ` — ${runningStage.label.toUpperCase()}` : ""}
          </div>
          {totalDurationMs != null && (
            <div className="text-[var(--text-muted)] text-[9px] mt-0.5">
              {(totalDurationMs / 1000).toFixed(1)}s ELAPSED
            </div>
          )}
        </div>
      )}

      {/* Navigation */}
      <nav className="flex-1 px-1 py-3 space-y-0.5">
        {navItems.map(({ href, label, key }) => {
          const isActive =
            href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center justify-between px-3 py-2 text-[11px] tracking-[.06em] transition-colors",
                isActive
                  ? "bg-[var(--accent-faint)] text-[var(--accent)]"
                  : "text-[var(--text-secondary)] hover:bg-[var(--surface-2)] hover:text-[var(--text-primary)]"
              )}
            >
              <span>{label}</span>
              <span className="text-[var(--text-muted)] text-[9px]">{key}</span>
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-[var(--border)] px-4 py-3">
        <div className="text-[var(--text-muted)] text-[9px] tracking-[.08em]">
          SESSION 19 — v2.0
        </div>
        <div className="text-[var(--text-muted)] text-[9px] mt-0.5 tracking-[.06em]">
          AU MARKET · JPAM
        </div>
      </div>
    </aside>
  );
}

