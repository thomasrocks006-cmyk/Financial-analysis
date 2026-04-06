"use client";

import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

interface MetricCardProps {
  label: string;
  value: string | number;
  icon?: ReactNode;
  trend?: "up" | "down" | "neutral";
  subtext?: string;
  className?: string;
  valueColor?: string;
}

export function MetricCard({
  label,
  value,
  trend,
  subtext,
  className,
  valueColor,
}: MetricCardProps) {
  const autoColor =
    trend === "up"
      ? "text-[var(--success)]"
      : trend === "down"
      ? "text-[var(--error)]"
      : "text-[var(--text-primary)]";

  return (
    <div
      className={cn(
        "border border-[var(--border)] bg-[var(--surface)] px-4 py-3",
        className
      )}
    >
      <div className="text-[var(--text-label)] text-[9px] tracking-[.1em] uppercase mb-2">
        {label}
      </div>
      <div className={cn("text-xl tabular-nums", valueColor ?? autoColor)}>
        {value}
        {trend === "up" && <span className="text-[var(--success)] text-xs ml-1">▲</span>}
        {trend === "down" && <span className="text-[var(--error)] text-xs ml-1">▼</span>}
      </div>
      {subtext && (
        <div className="text-[var(--text-muted)] text-[9px] mt-1 tracking-[.04em]">
          {subtext}
        </div>
      )}
    </div>
  );
}
