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
}

export function MetricCard({
  label,
  value,
  icon,
  trend,
  subtext,
  className,
}: MetricCardProps) {
  return (
    <div
      className={cn(
        "rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4",
        className
      )}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider">
          {label}
        </span>
        {icon && (
          <span className="text-[var(--text-muted)]">{icon}</span>
        )}
      </div>
      <div className="mt-2 flex items-baseline gap-2">
        <span className="text-2xl font-bold tabular-nums text-[var(--text-primary)]">
          {value}
        </span>
        {trend && (
          <span
            className={cn(
              "text-xs font-medium",
              trend === "up" && "text-green-400",
              trend === "down" && "text-red-400",
              trend === "neutral" && "text-[var(--text-muted)]"
            )}
          >
            {trend === "up" ? "↑" : trend === "down" ? "↓" : "—"}
          </span>
        )}
      </div>
      {subtext && (
        <p className="mt-1 text-xs text-[var(--text-muted)]">{subtext}</p>
      )}
    </div>
  );
}
