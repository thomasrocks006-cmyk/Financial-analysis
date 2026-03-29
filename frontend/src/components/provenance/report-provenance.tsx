/**
 * Report Section Provenance — shows traceability for each report section.
 *
 * Maps section titles to contributing stages, agents, and data sources.
 */

"use client";

import { useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  Layers,
  Tag,
  ShieldCheck,
  ShieldAlert,
  Shield,
} from "lucide-react";
import type { ReportSectionProvenance } from "@/lib/types";
import { STAGE_LABELS } from "@/lib/types";

interface Props {
  sections: ReportSectionProvenance[];
}

const confidenceConfig = {
  high: { icon: ShieldCheck, color: "text-emerald-400", bg: "bg-emerald-500/10" },
  medium: { icon: ShieldAlert, color: "text-yellow-400", bg: "bg-yellow-500/10" },
  low: { icon: Shield, color: "text-red-400", bg: "bg-red-500/10" },
};

export function ReportProvenancePanel({ sections }: Props) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

  if (!sections.length) {
    return (
      <div className="text-sm text-[var(--muted-foreground)] px-4 py-6 text-center">
        No report section provenance available.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold text-[var(--muted-foreground)] uppercase tracking-wider px-1 mb-3">
        Report Section Provenance ({sections.length} sections)
      </h3>
      {sections.map((section, idx) => {
        const isOpen = expandedIdx === idx;
        const conf = confidenceConfig[section.confidence_level] || confidenceConfig.medium;
        const ConfIcon = conf.icon;

        return (
          <div key={idx} className="bg-[var(--card)] border border-[var(--border)] rounded-lg overflow-hidden">
            <button
              onClick={() => setExpandedIdx(isOpen ? null : idx)}
              className="w-full flex items-center gap-3 px-4 py-3 hover:bg-[var(--muted)] transition-colors text-left"
            >
              {isOpen
                ? <ChevronDown className="w-4 h-4 text-[var(--muted-foreground)] shrink-0" />
                : <ChevronRight className="w-4 h-4 text-[var(--muted-foreground)] shrink-0" />}
              <span className="font-mono text-xs text-[var(--muted-foreground)] w-6">
                {section.section_index}
              </span>
              <span className="font-medium text-sm flex-1">{section.section_title}</span>
              <span className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded ${conf.bg} ${conf.color}`}>
                <ConfIcon className="w-3 h-3" />
                {section.confidence_level}
              </span>
            </button>

            {isOpen && (
              <div className="px-4 pb-4 pt-2 space-y-3 border-t border-[var(--border)]">
                {/* Source stages */}
                <div>
                  <h4 className="text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wider mb-1.5 flex items-center gap-1">
                    <Layers className="w-3 h-3" /> Source Stages
                  </h4>
                  <div className="flex flex-wrap gap-1.5">
                    {section.source_stages.map((s) => (
                      <span
                        key={s}
                        className="px-2 py-0.5 bg-blue-500/10 text-blue-400 rounded text-xs font-mono"
                      >
                        {s}: {STAGE_LABELS[s] || `Stage ${s}`}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Source agents */}
                {section.source_agents.length > 0 && (
                  <div>
                    <h4 className="text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wider mb-1.5">
                      agents
                    </h4>
                    <div className="flex flex-wrap gap-1.5">
                      {section.source_agents.map((a, i) => (
                        <span
                          key={i}
                          className="px-2 py-0.5 bg-purple-500/10 text-purple-400 rounded text-xs"
                        >
                          {a}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Methodology tags */}
                {section.methodology_tags.length > 0 && (
                  <div>
                    <h4 className="text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wider mb-1.5 flex items-center gap-1">
                      <Tag className="w-3 h-3" /> Methodology
                    </h4>
                    <div className="flex flex-wrap gap-1.5">
                      {section.methodology_tags.map((tag, i) => (
                        <span
                          key={i}
                          className="px-2 py-0.5 bg-cyan-500/10 text-cyan-400 rounded text-xs"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
