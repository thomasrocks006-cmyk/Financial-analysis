"""Phase 2.7 — ETF Overlap Engine: measure holdings overlap vs major AI/Tech ETFs."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ── ETF Reference Holdings (approximate weights, sum to ~100%) ──────────────
# Heuristic static profiles for major AI/tech ETFs; real data requires paid feed.
# Weights are in percentage points.

_ETF_HOLDINGS: dict[str, dict[str, float]] = {
    "BOTZ": {  # Global X Robotics & AI ETF
        "NVDA": 8.5, "AVGO": 3.2, "ABB": 5.1, "FANUC": 4.8, "KEYENCE": 4.2,
        "ISRG": 3.9, "SIEMENS": 2.8, "KUKA": 1.9, "COGNEX": 2.1, "TSM": 2.4,
    },
    "AIQ": {  # Global X AI & Technology ETF
        "NVDA": 6.2, "MSFT": 5.8, "GOOGL": 5.3, "META": 4.7, "AVGO": 3.9,
        "AMD": 3.1, "TSM": 2.8, "ORCL": 2.5, "CRM": 2.2, "ADBE": 2.0,
    },
    "SOXX": {  # iShares Semiconductor ETF
        "NVDA": 9.1, "AVGO": 8.7, "AMD": 5.4, "TSM": 4.9, "QCOM": 4.6,
        "INTC": 4.2, "MRVL": 3.8, "TXN": 3.5, "MU": 3.3, "AMAT": 3.1,
    },
    "XLK": {  # Technology Select Sector SPDR
        "MSFT": 22.4, "NVDA": 21.5, "AAPL": 18.3, "AVGO": 4.8, "AMD": 2.9,
        "ORCL": 2.4, "ADBE": 2.1, "AMAT": 1.9, "QCOM": 1.8, "CSCO": 1.7,
    },
    "ROBO": {  # ROBO Global Robotics & Automation ETF
        "IRBT": 1.8, "FANUC": 1.7, "YASK": 1.7, "ABB": 1.6, "ISRG": 1.6,
        "NVDA": 1.5, "KION": 1.5, "DANAHER": 1.4, "KEYENCE": 1.4, "COGNEX": 1.4,
    },
}


@dataclass
class ETFOverlapResult:
    """Overlap between a portfolio ticker and a single ETF."""
    ticker: str
    etf_name: str
    portfolio_weight_pct: float  # portfolio weight (0-100)
    etf_weight_pct: float        # ETF constituent weight (0-100)
    active_weight_pct: float     # portfolio - ETF weight
    is_benchmark_position: bool  # True if ETF weight > 0
    tracking_contribution: float  # contribution to tracking error (approx)


@dataclass
class PortfolioETFOverlap:
    """Full ETF overlap analysis for a portfolio."""
    run_id: str
    etf_name: str
    overlapping_tickers: list[str] = field(default_factory=list)
    overlap_weight_pct: float = 0.0        # sum of ETF weights in portfolio
    unique_weight_pct: float = 0.0         # sum of portfolio weights not in ETF
    weighted_overlap_score: float = 0.0    # portfolio-weighted similarity 0-100
    positions: list[ETFOverlapResult] = field(default_factory=list)


@dataclass
class UniverseOverlapReport:
    """Consolidated ETF overlap for all ETFs."""
    run_id: str
    portfolio_weights: dict[str, float]    # {ticker: pct}
    etf_overlaps: list[PortfolioETFOverlap] = field(default_factory=list)
    most_similar_etf: str = ""             # ETF with highest overlap
    max_overlap_score: float = 0.0
    differentiation_score: float = 100.0  # 100 = fully differentiated, 0 = ETF clone

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "most_similar_etf": self.most_similar_etf,
            "max_overlap_score": self.max_overlap_score,
            "differentiation_score": self.differentiation_score,
            "etf_overlaps": [
                {
                    "etf": o.etf_name,
                    "overlap_weight_pct": o.overlap_weight_pct,
                    "weighted_overlap_score": o.weighted_overlap_score,
                    "overlapping_tickers": o.overlapping_tickers,
                }
                for o in self.etf_overlaps
            ],
        }


class ETFOverlapEngine:
    """Measures portfolio overlap vs major AI/technology ETFs.

    Deterministic service — uses static heuristic ETF constituents by default.
    Intended to flag when portfolio construction is largely replicating a cheap ETF
    (i.e. low alpha potential) vs a truly differentiated high-conviction portfolio.
    """

    # ETFs to check against. Can be extended with live data feed.
    DEFAULT_ETF_UNIVERSE = list(_ETF_HOLDINGS.keys())

    def __init__(self, etf_holdings: dict[str, dict[str, float]] | None = None):
        """
        Args:
            etf_holdings: override default ETF constituent weights.
                          {etf_name: {ticker: weight_pct}}
        """
        self._holdings = etf_holdings or _ETF_HOLDINGS

    def _compute_overlap(
        self,
        run_id: str,
        etf_name: str,
        portfolio_weights: dict[str, float],
        etf_weights: dict[str, float],
    ) -> PortfolioETFOverlap:
        """Compute overlap metrics between a portfolio and a single ETF."""
        result = PortfolioETFOverlap(run_id=run_id, etf_name=etf_name)

        overlap_weight = 0.0
        total_port_weight = sum(portfolio_weights.values())

        for ticker, port_wt in portfolio_weights.items():
            etf_wt = etf_weights.get(ticker, 0.0)
            active_wt = port_wt - etf_wt
            is_bench = etf_wt > 0

            if is_bench:
                result.overlapping_tickers.append(ticker)
                overlap_weight += etf_wt

            # Approximate tracking contribution: squared active weight
            tracking_contrib = (active_wt ** 2) / max(total_port_weight, 1.0)

            result.positions.append(ETFOverlapResult(
                ticker=ticker,
                etf_name=etf_name,
                portfolio_weight_pct=port_wt,
                etf_weight_pct=etf_wt,
                active_weight_pct=active_wt,
                is_benchmark_position=is_bench,
                tracking_contribution=round(tracking_contrib, 4),
            ))

        result.overlap_weight_pct = round(overlap_weight, 2)
        result.unique_weight_pct = round(max(0, total_port_weight - overlap_weight), 2)

        # Weighted overlap score: how much of the ETF's weight is covered by this portfolio
        etf_total = sum(etf_weights.values()) or 1.0
        covered = sum(
            min(portfolio_weights.get(t, 0.0), etf_weights.get(t, 0.0))
            for t in set(list(portfolio_weights.keys()) + list(etf_weights.keys()))
        )
        result.weighted_overlap_score = round(covered / etf_total * 100, 1)

        return result

    def analyse_portfolio(
        self,
        run_id: str,
        portfolio_weights: dict[str, float],
        etfs_to_check: list[str] | None = None,
    ) -> UniverseOverlapReport:
        """Run full ETF overlap analysis for all requested ETFs.

        Args:
            run_id: pipeline run identifier
            portfolio_weights: {ticker: weight_pct}, weights should sum to ~100
            etfs_to_check: subset of ETF names to analyse; defaults to all available

        Returns:
            UniverseOverlapReport with per-ETF overlap data
        """
        etfs = etfs_to_check or self.DEFAULT_ETF_UNIVERSE
        report = UniverseOverlapReport(
            run_id=run_id,
            portfolio_weights=portfolio_weights,
        )

        for etf_name in etfs:
            etf_weights = self._holdings.get(etf_name)
            if etf_weights is None:
                logger.warning("ETF '%s' not found in holdings data — skipping", etf_name)
                continue
            overlap = self._compute_overlap(run_id, etf_name, portfolio_weights, etf_weights)
            report.etf_overlaps.append(overlap)

        if report.etf_overlaps:
            best = max(report.etf_overlaps, key=lambda o: o.weighted_overlap_score)
            report.most_similar_etf = best.etf_name
            report.max_overlap_score = best.weighted_overlap_score
            report.differentiation_score = round(100.0 - best.weighted_overlap_score, 1)

        logger.info(
            "ETF overlap [%s]: most similar=%s (%.1f%%), differentiation=%.1f%%",
            run_id,
            report.most_similar_etf,
            report.max_overlap_score,
            report.differentiation_score,
        )
        return report

    def get_overlap_summary(self, report: UniverseOverlapReport) -> str:
        """Return a human-readable summary for inclusion in research output."""
        lines = [
            f"ETF Overlap Analysis — Run {report.run_id}",
            f"Most similar ETF: {report.most_similar_etf} ({report.max_overlap_score:.1f}% overlap)",
            f"Differentiation score: {report.differentiation_score:.1f}/100",
            "",
            "Per-ETF overlap:",
        ]
        for overlap in sorted(report.etf_overlaps, key=lambda o: -o.weighted_overlap_score):
            lines.append(
                f"  {overlap.etf_name:6s} — {overlap.weighted_overlap_score:5.1f}% overlap "
                f"({', '.join(overlap.overlapping_tickers[:5]) or 'none'})"
            )
        return "\n".join(lines)

    def flag_etf_replication(
        self, report: UniverseOverlapReport, threshold_pct: float = 60.0
    ) -> bool:
        """Return True if portfolio is primarily replicating an ETF (differentiation < threshold)."""
        return report.differentiation_score < (100.0 - threshold_pct)
