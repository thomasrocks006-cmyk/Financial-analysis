"""A2 — Consensus & Reconciliation Service: compare FMP vs Finnhub, flag divergence."""

from __future__ import annotations

import logging
from typing import Optional

from research_pipeline.config.loader import ReconciliationThresholds
from research_pipeline.schemas.market_data import (
    ConsensusSnapshot,
    MarketSnapshot,
    ReconciliationField,
    ReconciliationReport,
    ReconciliationStatus,
)

logger = logging.getLogger(__name__)


class ConsensusReconciliationService:
    """Deterministic comparison of two data sources — no LLM.

    Classifies each field as green / amber / red based on divergence thresholds.
    """

    def __init__(self, thresholds: ReconciliationThresholds):
        self.thresholds = thresholds

    # ── helpers ─────────────────────────────────────────────────────────
    @staticmethod
    def _pct_diff(a: Optional[float], b: Optional[float]) -> Optional[float]:
        if a is None or b is None:
            return None
        if a == 0 and b == 0:
            return 0.0
        base = max(abs(a), abs(b))
        if base == 0:
            return None
        return abs(a - b) / base * 100

    def _classify(
        self, diff_pct: Optional[float], amber_thr: float, red_thr: float
    ) -> ReconciliationStatus:
        if diff_pct is None:
            # One or both values absent — distinct from an actual price divergence.
            # Callers that do not want to count this as AMBER should filter on MISSING.
            return ReconciliationStatus.MISSING
        if diff_pct >= red_thr:
            return ReconciliationStatus.RED
        if diff_pct >= amber_thr:
            return ReconciliationStatus.AMBER
        return ReconciliationStatus.GREEN

    # ── core reconciliation ────────────────────────────────────────────
    def reconcile_price(
        self, ticker: str, fmp: MarketSnapshot, finnhub_price: Optional[float]
    ) -> ReconciliationField:
        diff = self._pct_diff(fmp.price, finnhub_price)
        status = self._classify(
            diff,
            self.thresholds.price_drift_amber_pct,
            self.thresholds.price_drift_red_pct,
        )
        return ReconciliationField(
            field_name="price",
            ticker=ticker,
            source_a="fmp",
            source_a_value=fmp.price,
            source_b="finnhub",
            source_b_value=finnhub_price,
            preferred_source="fmp" if status == ReconciliationStatus.GREEN else "",
            divergence_pct=diff,
            status=status,
            reviewer_required=status == ReconciliationStatus.RED,
        )

    def reconcile_targets(
        self, ticker: str, fmp: ConsensusSnapshot, finnhub: ConsensusSnapshot
    ) -> list[ReconciliationField]:
        fields = []
        for attr_name, label in [
            ("target_low", "target_low"),
            ("target_median", "target_median"),
            ("target_high", "target_high"),
        ]:
            a_val = getattr(fmp, attr_name, None)
            b_val = getattr(finnhub, attr_name, None)
            diff = self._pct_diff(a_val, b_val)
            status = self._classify(
                diff,
                self.thresholds.target_divergence_amber_pct,
                self.thresholds.target_divergence_red_pct,
            )
            fields.append(ReconciliationField(
                field_name=label,
                ticker=ticker,
                source_a="fmp",
                source_a_value=a_val,
                source_b="finnhub",
                source_b_value=b_val,
                preferred_source="fmp",
                divergence_pct=diff,
                status=status,
                reviewer_required=status == ReconciliationStatus.RED,
            ))
        return fields

    def reconcile_ticker(
        self,
        ticker: str,
        fmp_quote: MarketSnapshot,
        fmp_consensus: ConsensusSnapshot,
        finnhub_consensus: ConsensusSnapshot,
        finnhub_price: Optional[float] = None,
    ) -> list[ReconciliationField]:
        """Reconcile all available fields for a single ticker."""
        results: list[ReconciliationField] = []
        # Price
        results.append(self.reconcile_price(ticker, fmp_quote, finnhub_price))
        # Targets
        results.extend(self.reconcile_targets(ticker, fmp_consensus, finnhub_consensus))
        return results

    def build_report(
        self,
        run_id: str,
        all_fields: list[ReconciliationField],
    ) -> ReconciliationReport:
        report = ReconciliationReport(run_id=run_id, fields=all_fields)
        missing_count = sum(1 for f in all_fields if f.status == ReconciliationStatus.MISSING)
        logger.info(
            "Reconciliation: %d fields — %d green, %d amber, %d red, %d missing",
            len(all_fields),
            len(all_fields) - report.amber_count - report.red_count - missing_count,
            report.amber_count,
            report.red_count,
            missing_count,
        )
        return report
