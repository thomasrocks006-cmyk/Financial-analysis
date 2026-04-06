/**
 * Full-page Provenance Panel — renders the complete provenance packet.
 *
 * Layout:
 *   - Completeness header (% coverage, stage count)
 *   - Per-stage ProvenanceCards (expandable)
 *   - Report section provenance
 */

"use client";

import { useQuery } from "@tanstack/react-query";
import { ShieldCheck, Layers, FileText, Loader2 } from "lucide-react";
import { getProvenance } from "@/lib/api";
import { ProvenanceCardComponent } from "./provenance-card";
import { ReportProvenancePanel } from "./report-provenance";
import type { ProvenancePacket } from "@/lib/types";

interface Props {
  runId: string;
}

export function ProvenancePanel({ runId }: Props) {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["provenance", runId],
    queryFn: () => getProvenance(runId),
    staleTime: 30_000,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12 text-[var(--text-muted)] text-[11px]">
        <Loader2 className="w-5 h-5 animate-spin mr-2" />
        Loading provenance data...
      </div>
    );
  }

  if (isError) {
    return (
      <div className="text-center py-12 text-red-400 text-sm">
        Failed to load provenance: {error instanceof Error ? error.message : "Unknown error"}
      </div>
    );
  }

  const packet: ProvenancePacket | null = data?.provenance ?? null;

  if (!packet || !packet.stage_cards?.length) {
    return (
      <div className="text-center py-12 text-[var(--text-muted)] text-sm">
        No provenance data available for this run.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Completeness header */}
      <div className="border border-[var(--border)] bg-[var(--surface)] p-4 flex items-center gap-6">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-5 h-5 text-[var(--success)]" />
          <span className="text-[10px] tracking-[.1em] text-[var(--text-label)] uppercase">Provenance Coverage</span>
        </div>
        <div className="flex-1">
          <div className="w-full bg-[var(--border-2)] h-2">
            <div
              className="bg-[var(--success)] h-2 transition-all"
              style={{ width: `${packet.completeness_pct}%` }}
            />
          </div>
        </div>
        <span className="text-sm font-mono text-[var(--text-primary)]">
          {packet.stages_with_provenance}/{packet.total_stages} stages ({packet.completeness_pct}%)
        </span>
      </div>

      {/* Stage provenance cards */}
      <div>
        <h3 className="text-[10px] tracking-[.1em] text-[var(--text-label)] uppercase px-1 mb-3 flex items-center gap-1">
          <Layers className="w-4 h-4" /> Stage Provenance ({packet.stage_cards.length})
        </h3>
        <div className="space-y-2">
          {packet.stage_cards
            .sort((a, b) => a.stage_num - b.stage_num)
            .map((card) => (
              <ProvenanceCardComponent key={card.stage_num} card={card} />
            ))}
        </div>
      </div>

      {/* Report section provenance */}
      {packet.report_sections && packet.report_sections.length > 0 && (
        <div>
          <div className="flex items-center gap-1 text-[10px] tracking-[.1em] text-[var(--text-label)] uppercase px-1 mb-3">
            <FileText className="w-4 h-4" /> Report Section Traceability
          </div>
          <ReportProvenancePanel sections={packet.report_sections} />
        </div>
      )}
    </div>
  );
}
