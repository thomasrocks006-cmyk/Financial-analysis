/* ── API types matching the FastAPI backend schemas ─────────────────── */

export interface RunRequest {
  universe: string[];
  run_label?: string;
  llm_model?: string;
  llm_temperature?: number;
  max_positions?: number;
  benchmark_ticker?: string;
  portfolio_variants?: string[];
  market?: "us" | "au" | "global" | "mixed";
  client_profile?: ClientProfile | null;
}

export type OrchestrationMode = "auto" | "single";

export interface ClientProfile {
  name: string;
  primary_objective: string;
  risk_tolerance: "conservative" | "moderate" | "aggressive";
  time_horizon_years: number;
  investment_amount_usd: number;
  esg_mandate: boolean;
  exclude_tobacco: boolean;
  exclude_weapons: boolean;
  exclude_fossil_fuel: boolean;
  min_market_cap_bn: number;
  benchmark: string;
  special_instructions: string;
}

export interface PipelineEvent {
  run_id: string;
  event_type: PipelineEventType;
  timestamp: string;
  stage: number | null;
  stage_label: string | null;
  agent_name: string | null;
  duration_ms: number | null;
  data: Record<string, unknown>;
}

export type PipelineEventType =
  | "pipeline_started"
  | "stage_started"
  | "stage_completed"
  | "stage_failed"
  | "agent_started"
  | "agent_completed"
  | "llm_call_started"
  | "llm_call_completed"
  | "artifact_written"
  | "pipeline_completed"
  | "pipeline_failed";

export type RunStatus = "queued" | "running" | "completed" | "failed" | "cancelled";

export interface RunSummary {
  run_id: string;
  status: RunStatus;
  run_label: string | null;
  universe: string[];
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error?: string | null;
  has_result?: boolean;
}

export interface StageInfo {
  stage_num: number;
  stage_label: string;
  status: "pending" | "running" | "completed" | "failed" | "skipped";
  duration_ms: number;
  gate_passed: boolean | null;
  gate_reason: string;
  output: Record<string, unknown>;
  has_output: boolean;
}

export interface TimingData {
  stage_latencies_ms: Record<string, number>;
  total_pipeline_duration_s: number;
}

export interface AuditPacket {
  run_id: string;
  quality_score: number;
  gates_passed: number[];
  gates_failed: number[];
  blockers: string[];
  agents_succeeded: string[];
  agents_failed: string[];
  total_claims: number;
  pass_claims: number;
  caveat_claims: number;
  fail_claims: number;
  tier1_claims: number;
  tier2_claims: number;
  tier3_claims: number;
  tier4_claims: number;
  ic_approved: boolean | null;
  ic_vote_breakdown: Record<string, string>;
  mandate_compliant: boolean | null;
  esg_exclusions: string[];
  stage_latencies_ms: Record<string, number>;
  total_pipeline_duration_s: number;
  rebalancing_summary: Record<string, unknown>;
  [key: string]: unknown;
}

export interface SavedRun {
  run_id: string;
  tickers: string[];
  model: string;
  completed_at: string;
  success: boolean;
  publication_status: string;
  word_count: number;
  json_path: string | null;
  md_path: string | null;
}

export interface Artifact {
  filename: string;
  size_bytes: number;
  path: string;
}

/* ── Session 17: Provenance types ────────────────────────────────── */

export interface DataSource {
  name: string;
  source_type: string;
  stage_origin: number | null;
  freshness: string | null;
  confidence: number | null;
}

export interface StageOutput {
  name: string;
  output_type: string;
  description: string;
  artifact_path: string | null;
}

export interface ProvenanceCard {
  stage_num: number;
  stage_label: string;
  run_id: string;
  timestamp: string;
  agent_name: string | null;
  model_used: string | null;
  model_temperature: number | null;
  inputs: DataSource[];
  outputs: StageOutput[];
  gate_passed: boolean | null;
  gate_reason: string;
  gate_blockers: string[];
  assumptions: string[];
  duration_ms: number;
  error: string | null;
}

export interface ReportSectionProvenance {
  section_title: string;
  section_index: number;
  source_stages: number[];
  source_agents: string[];
  data_sources: DataSource[];
  confidence_level: "low" | "medium" | "high";
  methodology_tags: string[];
}

export interface ProvenancePacket {
  run_id: string;
  created_at: string;
  stage_cards: ProvenanceCard[];
  report_sections: ReportSectionProvenance[];
  total_stages: number;
  stages_with_provenance: number;
  completeness_pct: number;
}

export const STAGE_LABELS: Record<number, string> = {
  0: "Bootstrap",
  1: "Universe Validation",
  2: "Data Ingestion",
  3: "Reconciliation",
  4: "Data QA",
  5: "Evidence Library",
  6: "Sector Analysis",
  7: "Valuation",
  8: "Macro & Geopolitical",
  9: "Risk Assessment",
  10: "Red Team",
  11: "Associate Review",
  12: "Portfolio Construction",
  13: "Report Assembly",
  14: "Monitoring",
};

export const STAGE_COUNT = 15;

/* ── Session 18: Quant Analytics types ──────────────────────────────── */

export interface QuantData {
  run_id: string;
  // Market risk (Stage 9)
  var_analysis: Record<string, number>;
  drawdown_analysis: Record<string, number>;
  portfolio_volatility: number;
  var_method: string;
  confidence_level: number;
  // ETF overlap (Stage 9)
  etf_overlap: Record<string, unknown>;
  etf_differentiation_score: number | null;
  // Factor exposures (Stage 9)
  factor_exposures: Array<Record<string, unknown>>;
  portfolio_factor_exposure: Record<string, number>;
  // Fixed income context (Stage 9)
  fixed_income_context: Record<string, unknown>;
  // IC record (Stage 12)
  ic_record: Record<string, unknown>;
  // Mandate compliance (Stage 12)
  mandate_compliance: Record<string, unknown>;
  // Portfolio weights (Stage 12)
  baseline_weights: Record<string, number>;
  // Optimisation (Stage 12)
  optimisation_results: Record<string, unknown>;
  // Rebalancing (Stage 12)
  rebalance_proposal: Record<string, unknown> | null;
  // BHB attribution (Stage 14)
  attribution: Record<string, unknown>;
  // ESG (Stage 6)
  esg_scores: Array<Record<string, unknown>>;
}
