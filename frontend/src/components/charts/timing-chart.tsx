"use client";

import { cn } from "@/lib/utils";
import { STAGE_LABELS } from "@/lib/types";
import { formatDuration } from "@/lib/utils";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

interface TimingChartProps {
  timings: Record<string, number>; // "stage_0" -> ms
  className?: string;
}

export function TimingChart({ timings, className }: TimingChartProps) {
  const data = Object.entries(timings)
    .map(([key, ms]) => {
      const num = parseInt(key.replace("stage_", ""), 10);
      return {
        stage: `S${num}`,
        label: STAGE_LABELS[num] || `Stage ${num}`,
        ms,
        seconds: ms / 1000,
      };
    })
    .sort((a, b) => {
      const aNum = parseInt(a.stage.replace("S", ""), 10);
      const bNum = parseInt(b.stage.replace("S", ""), 10);
      return aNum - bNum;
    });

  if (data.length === 0) {
    return (
      <div className={cn("border border-[var(--border)] bg-[var(--surface)] p-6 text-center text-sm text-[var(--text-muted)]", className)}>
        No timing data available
      </div>
    );
  }

  return (
    <div className={cn("border border-[var(--border)] bg-[var(--surface)] p-4", className)}>
      <h3 className="mb-4 text-[10px] tracking-[.1em] text-[var(--text-label)] uppercase">
        Stage Execution Times
      </h3>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data} margin={{ top: 5, right: 10, left: 10, bottom: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis
            dataKey="stage"
            tick={{ fontSize: 11, fill: "var(--text-muted)" }}
            tickLine={{ stroke: "var(--border)" }}
          />
          <YAxis
            tick={{ fontSize: 11, fill: "var(--text-muted)" }}
            tickLine={{ stroke: "var(--border)" }}
            label={{
              value: "seconds",
              angle: -90,
              position: "insideLeft",
              style: { fontSize: 11, fill: "var(--text-muted)" },
            }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "var(--surface-2)",
              border: "1px solid var(--border)",
              fontSize: 12,
              color: "var(--text-primary)",
            }}
            formatter={(value) => [formatDuration(Number(value || 0) * 1000), "Duration"]}
            labelFormatter={(label) => {
              const item = data.find((d) => d.stage === label);
              return item?.label || label;
            }}
          />
          <Bar dataKey="seconds">
            {data.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={entry.seconds > 30 ? "var(--warning)" : "var(--accent)"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
