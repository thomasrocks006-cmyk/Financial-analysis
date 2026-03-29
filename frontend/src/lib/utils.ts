import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  const mins = Math.floor(ms / 60000);
  const secs = ((ms % 60000) / 1000).toFixed(0);
  return `${mins}m ${secs}s`;
}

export function formatCost(usd: number): string {
  if (usd === 0) return "$0.00";
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  return `$${usd.toFixed(2)}`;
}

export function formatNumber(n: number): string {
  return new Intl.NumberFormat("en-US").format(n);
}

export function formatTimestamp(iso: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function stageStatusColor(status: string): string {
  switch (status) {
    case "completed":
    case "done":
      return "text-green-400";
    case "running":
      return "text-blue-400";
    case "failed":
      return "text-red-400";
    case "skipped":
      return "text-gray-500";
    default:
      return "text-gray-600";
  }
}

export function stageStatusIcon(status: string): string {
  switch (status) {
    case "completed":
    case "done":
      return "✓";
    case "running":
      return "●";
    case "failed":
      return "✗";
    case "skipped":
      return "—";
    default:
      return "○";
  }
}
