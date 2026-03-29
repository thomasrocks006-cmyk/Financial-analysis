/**
 * Provenance Card — displays per-stage lineage details.
 *
 * Shows inputs consumed, outputs produced, gate outcome,
 * assumptions, timing, and model used for a single pipeline stage.
 */

"use client";

import { useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  Database,
  Upload,
  ShieldCheck,
  ShieldX,
  AlertTriangle,
  Clock,
  Cpu,
  GitBranch,
} from "lucide-react";
import type { ProvenanceCard as ProvenanceCardType } from "@/lib/types";
import { formatDuration } from "@/lib/utils";

interface ProvenanceCardProps {
  card: ProvenanceCardType;
}

export function ProvenanceCardComponent({ card }: ProvenanceCardProps) {
  const [expanded, setExpanded] = useState(false);

  const gateIcon = card.gate_passed === true
    ? <ShieldCheck className="w-4 h-4 text-emerald-400" />
    : card.gate_passed === false
    ? <ShieldX className="w-4 h-4 text-red-400" />
    : <AlertTriangle className="w-4 h-4 text-yellow-400" />;

  const gateLabel = card.gate_passed === true
    ? "Passed" : card.gate_passed === false
    ? "Failed" : "N/A";

  return (
    <div className="bg-[var(--card)] border border-[var(--border)] rounded-lg overflow-hidden">
      {/* Header — always visible */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-[var(--muted)] transition-colors text-left"
      >
        {expanded
          ? <ChevronDown className="w-4 h-4 text-[var(--muted-foreground)] shrink-0" />
          : <ChevronRight className="w-4 h-4 text-[var(--muted-foreground)] shrink-0" />}

        <span className="font-mono text-xs text-[var(--muted-foreground)] w-6">
          {card.stage_num}
        </span>
        <span className="font-medium text-sm flex-1">{card.stage_label}</span>

        <span className="flex items-center gap-1 text-xs">{gateIcon} {gateLabel}</span>
        <span className="flex items-center gap-1 text-xs text-[var(--muted-foreground)]">
          <Clock className="w-3 h-3" />
          {formatDuration(card.duration_ms)}
        </span>
      </button>

      {/* Expanded details */}
      {expanded && (
        <div className="px-4 pb-4 space-y-4 border-t border-[var(--border)]">
          {/* Agent & model info */}
          <div className="flex flex-wrap gap-4 pt-3 text-xs text-[var(--muted-foreground)]">
            {card.agent_name && (
              <span className="flex items-center gap-1">
                <Cpu className="w-3 h-3" /> Agent: <span className="text-[var(--foreground)]">{card.agent_name}</span>
              </span>
            )}
            {card.model_used && (
              <span className="flex items-center gap-1">
                Model: <span className="text-[var(--foreground)]">{card.model_used}</span>
              </span>
            )}
            {card.model_temperature != null && (
              <span>Temp: {card.model_temperature}</span>
            )}
          </div>

          {/* Inputs */}
          {card.inputs.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wider mb-2 flex items-center gap-1">
                <Database className="w-3 h-3" /> Inputs ({card.inputs.length})
              </h4>
              <div className="space-y-1">
                {card.inputs.map((input, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs">
                    <span className="px-1.5 py-0.5 bg-blue-500/10 text-blue-400 rounded font-mono">
                      {input.source_type}
                    </span>
                    <span>{input.name}</span>
                    {input.stage_origin != null && (
                      <span className="text-[var(--muted-foreground)]">
                        <GitBranch className="w-3 h-3 inline" /> from stage {input.stage_origin}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Outputs */}
          {card.outputs.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wider mb-2 flex items-center gap-1">
                <Upload className="w-3 h-3" /> Outputs ({card.outputs.length})
              </h4>
              <div className="space-y-1">
                {card.outputs.map((output, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs">
                    <span className="px-1.5 py-0.5 bg-emerald-500/10 text-emerald-400 rounded font-mono">
                      {output.output_type}
                    </span>
                    <span>{output.name}</span>
                    {output.description && (
                      <span className="text-[var(--muted-foreground)]">— {output.description}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Gate details */}
          {card.gate_reason && (
            <div>
              <h4 className="text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wider mb-1">
                Gate Reason
              </h4>
              <p className="text-xs">{card.gate_reason}</p>
              {card.gate_blockers.length > 0 && (
                <div className="mt-1 space-y-0.5">
                  {card.gate_blockers.map((b, i) => (
                    <div key={i} className="text-xs text-red-400 flex items-center gap-1">
                      <AlertTriangle className="w-3 h-3" /> {b}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Assumptions */}
          {card.assumptions.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wider mb-1">
                Assumptions ({card.assumptions.length})
              </h4>
              <ul className="list-disc list-inside space-y-0.5">
                {card.assumptions.map((a, i) => (
                  <li key={i} className="text-xs text-yellow-300/80">{a}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Error */}
          {card.error && (
            <div className="p-2 bg-red-500/10 border border-red-500/20 rounded text-xs text-red-400">
              Error: {card.error}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
