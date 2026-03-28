"""Performance Tracker — historical portfolio NAV and return tracking."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np

from research_pipeline.schemas.performance import (
    BHBAttribution,
    BenchmarkComparison,
    DrawdownAnalysis,
    LiquidityProfile,
    PortfolioSnapshot,
    ThesisRecord,
    ThesisStatus,
)

logger = logging.getLogger(__name__)


class PerformanceTracker:
    """Track portfolio performance over time — no LLM.

    Persists portfolio snapshots, computes NAV evolution,
    and provides Brinson-Hood-Beebower attribution.
    """

    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir / "performance"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._snapshots_file = self.storage_dir / "snapshots.json"
        self._theses_file = self.storage_dir / "theses.json"

    # ── Snapshot Management ────────────────────────────────────────────
    def save_snapshot(self, snapshot: PortfolioSnapshot) -> None:
        """Persist a portfolio snapshot for future attribution."""
        snapshots = self._load_snapshots()
        snapshots.append(snapshot.model_dump(mode="json"))
        self._write_json(self._snapshots_file, snapshots)
        logger.info("Portfolio snapshot saved for run %s (%s)", snapshot.run_id, snapshot.variant_name)

    def get_snapshots(
        self, variant_name: str | None = None, limit: int = 100
    ) -> list[PortfolioSnapshot]:
        """Load historical snapshots."""
        raw = self._load_snapshots()
        snapshots = [PortfolioSnapshot.model_validate(s) for s in raw]
        if variant_name:
            snapshots = [s for s in snapshots if s.variant_name == variant_name]
        return sorted(snapshots, key=lambda s: s.snapshot_date, reverse=True)[:limit]

    # ── BHB Attribution ────────────────────────────────────────────────
    def compute_bhb_attribution(
        self,
        run_id: str,
        portfolio_weights: dict[str, float],
        portfolio_returns: dict[str, float],
        benchmark_weights: dict[str, float],
        benchmark_returns: dict[str, float],
        sector_map: dict[str, str],
        period_start: datetime | None = None,
        period_end: datetime | None = None,
    ) -> BHBAttribution:
        """Compute Brinson-Hood-Beebower attribution.

        Decomposes excess return into:
        - Allocation effect: being overweight/underweight in sectors that perform well/poorly
        - Selection effect: picking better/worse stocks within a sector
        - Interaction effect: cross-term
        """
        now = datetime.now(timezone.utc)

        # Aggregate to sector level
        sectors = set(sector_map.values())
        sector_port_w: dict[str, float] = {}
        sector_bench_w: dict[str, float] = {}
        sector_port_r: dict[str, float] = {}
        sector_bench_r: dict[str, float] = {}

        for sector in sectors:
            # Portfolio sector weight and return
            p_tickers = [t for t, s in sector_map.items() if s == sector and t in portfolio_weights]
            p_weight = sum(portfolio_weights.get(t, 0) for t in p_tickers)
            p_return = sum(
                portfolio_returns.get(t, 0) * portfolio_weights.get(t, 0)
                for t in p_tickers
            )
            p_return = p_return / p_weight if p_weight > 0 else 0

            # Benchmark sector weight and return
            b_tickers = [t for t, s in sector_map.items() if s == sector and t in benchmark_weights]
            b_weight = sum(benchmark_weights.get(t, 0) for t in b_tickers)
            b_return = sum(
                benchmark_returns.get(t, 0) * benchmark_weights.get(t, 0)
                for t in b_tickers
            )
            b_return = b_return / b_weight if b_weight > 0 else 0

            sector_port_w[sector] = p_weight
            sector_bench_w[sector] = b_weight
            sector_port_r[sector] = p_return
            sector_bench_r[sector] = b_return

        # Total benchmark return
        total_bench_r = sum(
            sector_bench_w.get(s, 0) * sector_bench_r.get(s, 0)
            for s in sectors
        ) / max(sum(sector_bench_w.values()), 1)

        total_port_r = sum(
            sector_port_w.get(s, 0) * sector_port_r.get(s, 0)
            for s in sectors
        ) / max(sum(sector_port_w.values()), 1)

        # BHB decomposition per sector
        allocation_effects: dict[str, float] = {}
        selection_effects: dict[str, float] = {}

        total_allocation = 0.0
        total_selection = 0.0
        total_interaction = 0.0

        for sector in sectors:
            pw = sector_port_w.get(sector, 0) / 100  # convert to fraction
            bw = sector_bench_w.get(sector, 0) / 100
            pr = sector_port_r.get(sector, 0)
            br = sector_bench_r.get(sector, 0)

            alloc = (pw - bw) * (br - total_bench_r)
            select = bw * (pr - br)
            interact = (pw - bw) * (pr - br)

            allocation_effects[sector] = round(alloc * 100, 4)
            selection_effects[sector] = round(select * 100, 4)

            total_allocation += alloc
            total_selection += select
            total_interaction += interact

        return BHBAttribution(
            run_id=run_id,
            period_start=period_start or now,
            period_end=period_end or now,
            total_portfolio_return_pct=round(total_port_r * 100, 4),
            total_benchmark_return_pct=round(total_bench_r * 100, 4),
            excess_return_pct=round((total_port_r - total_bench_r) * 100, 4),
            allocation_effect_pct=round(total_allocation * 100, 4),
            selection_effect_pct=round(total_selection * 100, 4),
            interaction_effect_pct=round(total_interaction * 100, 4),
            sector_allocation=allocation_effects,
            sector_selection=selection_effects,
        )

    # ── Liquidity Profiling ────────────────────────────────────────────
    def compute_liquidity_profile(
        self,
        ticker: str,
        avg_daily_volume: float,
        price: float,
        position_weight_pct: float,
        portfolio_value: float = 1_000_000.0,
        participation_rate: float = 0.20,
    ) -> LiquidityProfile:
        """Compute liquidity metrics for a position."""
        position_value = portfolio_value * position_weight_pct / 100
        adv_value = avg_daily_volume * price
        days_to_liquidate = position_value / (adv_value * participation_rate) if adv_value > 0 else 999

        # Market impact estimate (square root model)
        if adv_value > 0:
            participation = position_value / adv_value
            impact_bps = 10 * np.sqrt(participation) * 100
        else:
            impact_bps = 999

        # Liquidity score (10 = most liquid)
        if days_to_liquidate <= 0.5:
            score = 10.0
        elif days_to_liquidate <= 1:
            score = 9.0
        elif days_to_liquidate <= 3:
            score = 7.0
        elif days_to_liquidate <= 5:
            score = 5.0
        elif days_to_liquidate <= 10:
            score = 3.0
        else:
            score = 1.0

        return LiquidityProfile(
            ticker=ticker,
            avg_daily_volume=avg_daily_volume,
            avg_daily_value=round(adv_value, 2),
            position_value=round(position_value, 2),
            days_to_liquidate=round(days_to_liquidate, 2),
            liquidity_score=score,
            market_impact_estimate_bps=round(float(impact_bps), 2),
        )

    # ── Thesis Tracking ────────────────────────────────────────────────
    def create_thesis(
        self,
        thesis_id: str,
        run_id: str,
        ticker: str,
        thesis_text: str,
        price_at_creation: float | None = None,
        claim_ids: list[str] | None = None,
    ) -> ThesisRecord:
        """Create and persist a new thesis record."""
        thesis = ThesisRecord(
            thesis_id=thesis_id,
            run_id=run_id,
            ticker=ticker,
            thesis_text=thesis_text,
            price_at_creation=price_at_creation,
            claim_ids=claim_ids or [],
        )
        theses = self._load_theses()
        theses.append(thesis.model_dump(mode="json"))
        self._write_json(self._theses_file, theses)
        return thesis

    def update_thesis_status(
        self,
        thesis_id: str,
        status: ThesisStatus,
        current_price: float | None = None,
        notes: str = "",
    ) -> ThesisRecord | None:
        """Update a thesis status (confirmed, challenged, invalidated)."""
        theses = self._load_theses()
        for t in theses:
            if t.get("thesis_id") == thesis_id:
                t["status"] = status.value
                t["last_reviewed"] = datetime.now(timezone.utc).isoformat()
                if current_price is not None:
                    t["current_price"] = current_price
                    if t.get("price_at_creation"):
                        t["return_since_pct"] = round(
                            (current_price / t["price_at_creation"] - 1) * 100, 2
                        )
                if notes:
                    t["notes"] = notes
                self._write_json(self._theses_file, theses)
                return ThesisRecord.model_validate(t)
        return None

    def get_active_theses(self, ticker: str | None = None) -> list[ThesisRecord]:
        """Get all active theses, optionally filtered by ticker."""
        theses = self._load_theses()
        records = [ThesisRecord.model_validate(t) for t in theses]
        records = [t for t in records if t.status == ThesisStatus.ACTIVE]
        if ticker:
            records = [t for t in records if t.ticker == ticker]
        return records

    # ── Persistence ────────────────────────────────────────────────────
    def _load_snapshots(self) -> list[dict]:
        if self._snapshots_file.exists():
            return json.loads(self._snapshots_file.read_text())
        return []

    def _load_theses(self) -> list[dict]:
        if self._theses_file.exists():
            return json.loads(self._theses_file.read_text())
        return []

    def _write_json(self, path: Path, data: list) -> None:
        path.write_text(json.dumps(data, indent=2, default=str))
