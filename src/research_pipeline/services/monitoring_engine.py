"""Monitoring Engine — daily portfolio drift detection, alerts, and re-analysis triggers."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ── Alert Models ────────────────────────────────────────────────────────────


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(str, Enum):
    PRICE_MOVE = "price_move"
    WEIGHT_DRIFT = "weight_drift"
    CONCENTRATION_BREACH = "concentration_breach"
    NEWS_MATERIAL = "news_material"
    THESIS_CHALLENGED = "thesis_challenged"
    MANDATE_NEAR_BREACH = "mandate_near_breach"
    VOLATILITY_SPIKE = "volatility_spike"


class MonitoringAlert(BaseModel):
    """A single monitoring alert."""

    alert_id: str
    run_id: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    alert_type: AlertType
    severity: AlertSeverity
    ticker: str = ""
    headline: str
    details: dict[str, Any] = {}
    requires_action: bool = False
    suggested_action: str = ""


class MonitoringReport(BaseModel):
    """Daily monitoring report."""

    report_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    run_id: str = ""
    alerts: list[MonitoringAlert] = []
    portfolio_summary: dict[str, Any] = {}
    positions_reviewed: int = 0

    @property
    def critical_count(self) -> int:
        return sum(1 for a in self.alerts if a.severity == AlertSeverity.CRITICAL)

    @property
    def warning_count(self) -> int:
        return sum(1 for a in self.alerts if a.severity == AlertSeverity.WARNING)

    @property
    def needs_reanalysis(self) -> bool:
        return self.critical_count > 0


class MonitoringEngine:
    """Portfolio monitoring and alert generation — no LLM.

    Compares current portfolio state against reference weights,
    detects drift, price moves, and concentration changes.
    """

    def __init__(
        self,
        price_move_threshold_pct: float = 5.0,
        weight_drift_threshold_pct: float = 2.0,
        concentration_hhi_limit: float = 2500,
        max_single_name_pct: float = 15.0,
        atr_multiplier: float = 2.0,
    ):
        self.price_move_threshold = price_move_threshold_pct
        self.weight_drift_threshold = weight_drift_threshold_pct
        self.hhi_limit = concentration_hhi_limit
        self.max_single_name = max_single_name_pct
        self.atr_multiplier = atr_multiplier
        self._alert_counter = 0

    def _next_alert_id(self, run_id: str) -> str:
        self._alert_counter += 1
        return f"MON-{run_id}-{self._alert_counter:04d}"

    def run_monitoring(
        self,
        run_id: str,
        target_weights: dict[str, float],
        current_prices: dict[str, float],
        reference_prices: dict[str, float],
        volume_data: dict[str, float] | None = None,
        atr_data: dict[str, float] | None = None,
    ) -> MonitoringReport:
        """Run full monitoring check and generate alerts.

        Args:
            run_id: Pipeline run identifier
            target_weights: Target portfolio weights (ticker -> pct)
            current_prices: Current prices (ticker -> price)
            reference_prices: Reference prices at portfolio construction (ticker -> price)
            volume_data: Average daily volume per ticker (optional)
            atr_data: Average True Range per ticker (optional)
        """
        alerts: list[MonitoringAlert] = []
        self._alert_counter = 0

        # 1. Price move checks
        price_alerts = self._check_price_moves(
            run_id, target_weights, current_prices, reference_prices, atr_data
        )
        alerts.extend(price_alerts)

        # 2. Weight drift (due to price changes)
        drift_alerts, current_weights = self._check_weight_drift(
            run_id, target_weights, current_prices, reference_prices
        )
        alerts.extend(drift_alerts)

        # 3. Concentration check on drifted weights
        conc_alerts = self._check_concentration(run_id, current_weights)
        alerts.extend(conc_alerts)

        # 4. Volatility spike detection
        if atr_data and reference_prices:
            vol_alerts = self._check_volatility_spikes(
                run_id, current_prices, reference_prices, atr_data
            )
            alerts.extend(vol_alerts)

        # Build summary
        total_value_change = 0.0
        for ticker in target_weights:
            if ticker in current_prices and ticker in reference_prices:
                weight = target_weights[ticker] / 100
                price_change = (current_prices[ticker] / reference_prices[ticker]) - 1
                total_value_change += weight * price_change

        report = MonitoringReport(
            run_id=run_id,
            alerts=alerts,
            positions_reviewed=len(target_weights),
            portfolio_summary={
                "total_positions": len(target_weights),
                "total_alerts": len(alerts),
                "critical_alerts": sum(1 for a in alerts if a.severity == AlertSeverity.CRITICAL),
                "estimated_return_since_construction_pct": round(total_value_change * 100, 2),
            },
        )

        logger.info(
            "Monitoring: %d alerts (%d critical) for %d positions",
            len(alerts),
            report.critical_count,
            len(target_weights),
        )
        return report

    def _check_price_moves(
        self,
        run_id: str,
        weights: dict[str, float],
        current: dict[str, float],
        reference: dict[str, float],
        atr_data: dict[str, float] | None,
    ) -> list[MonitoringAlert]:
        alerts: list[MonitoringAlert] = []
        for ticker in weights:
            if ticker not in current or ticker not in reference:
                continue
            pct_change = ((current[ticker] / reference[ticker]) - 1) * 100

            # ATR-based threshold if available
            threshold = self.price_move_threshold
            if atr_data and ticker in atr_data and reference[ticker] > 0:
                atr_pct = (atr_data[ticker] / reference[ticker]) * 100
                threshold = max(threshold, atr_pct * self.atr_multiplier)

            if abs(pct_change) >= threshold:
                severity = (
                    AlertSeverity.CRITICAL
                    if abs(pct_change) >= threshold * 2
                    else AlertSeverity.WARNING
                )
                direction = "up" if pct_change > 0 else "down"
                alerts.append(
                    MonitoringAlert(
                        alert_id=self._next_alert_id(run_id),
                        run_id=run_id,
                        alert_type=AlertType.PRICE_MOVE,
                        severity=severity,
                        ticker=ticker,
                        headline=f"{ticker} moved {pct_change:+.1f}% ({direction}) since construction",
                        details={
                            "reference_price": reference[ticker],
                            "current_price": current[ticker],
                            "pct_change": round(pct_change, 2),
                            "threshold": round(threshold, 2),
                        },
                        requires_action=severity == AlertSeverity.CRITICAL,
                        suggested_action=f"Review thesis for {ticker}; consider rebalance"
                        if severity == AlertSeverity.CRITICAL
                        else "",
                    )
                )
        return alerts

    def _check_weight_drift(
        self,
        run_id: str,
        target_weights: dict[str, float],
        current_prices: dict[str, float],
        reference_prices: dict[str, float],
    ) -> tuple[list[MonitoringAlert], dict[str, float]]:
        """Compute drifted weights from price changes and flag significant drift."""
        alerts: list[MonitoringAlert] = []

        # Compute current value-weighted positions
        position_values: dict[str, float] = {}
        for ticker, weight in target_weights.items():
            if ticker in current_prices and ticker in reference_prices:
                price_ratio = current_prices[ticker] / reference_prices[ticker]
                position_values[ticker] = weight * price_ratio
            else:
                position_values[ticker] = weight

        total_value = sum(position_values.values())
        current_weights = (
            {
                t: round((v / total_value) * 100 if total_value > 0 else 0, 2)
                for t, v in position_values.items()
            }
            if total_value > 0
            else dict(target_weights)
        )

        for ticker in target_weights:
            drift = abs(current_weights.get(ticker, 0) - target_weights[ticker])
            if drift >= self.weight_drift_threshold:
                severity = (
                    AlertSeverity.CRITICAL
                    if drift >= self.weight_drift_threshold * 3
                    else AlertSeverity.WARNING
                )
                alerts.append(
                    MonitoringAlert(
                        alert_id=self._next_alert_id(run_id),
                        run_id=run_id,
                        alert_type=AlertType.WEIGHT_DRIFT,
                        severity=severity,
                        ticker=ticker,
                        headline=f"{ticker} drifted {drift:.1f}pp from target ({target_weights[ticker]:.1f}% → {current_weights.get(ticker, 0):.1f}%)",
                        details={
                            "target_weight": target_weights[ticker],
                            "current_weight": current_weights.get(ticker, 0),
                            "drift_pp": round(drift, 2),
                        },
                        requires_action=severity == AlertSeverity.CRITICAL,
                        suggested_action="Rebalance to target weights"
                        if severity == AlertSeverity.CRITICAL
                        else "",
                    )
                )

        return alerts, current_weights

    def _check_concentration(self, run_id: str, weights: dict[str, float]) -> list[MonitoringAlert]:
        alerts: list[MonitoringAlert] = []

        # HHI check
        hhi = sum(w**2 for w in weights.values())
        if hhi > self.hhi_limit:
            alerts.append(
                MonitoringAlert(
                    alert_id=self._next_alert_id(run_id),
                    run_id=run_id,
                    alert_type=AlertType.CONCENTRATION_BREACH,
                    severity=AlertSeverity.CRITICAL,
                    headline=f"Portfolio HHI={hhi:.0f} exceeds limit {self.hhi_limit}",
                    details={"hhi": round(hhi, 0), "limit": self.hhi_limit},
                    requires_action=True,
                    suggested_action="Reduce concentration — diversify positions",
                )
            )

        # Single name check
        for ticker, w in weights.items():
            if w > self.max_single_name:
                alerts.append(
                    MonitoringAlert(
                        alert_id=self._next_alert_id(run_id),
                        run_id=run_id,
                        alert_type=AlertType.CONCENTRATION_BREACH,
                        severity=AlertSeverity.CRITICAL,
                        ticker=ticker,
                        headline=f"{ticker} weight {w:.1f}% exceeds single-name limit {self.max_single_name}%",
                        details={"weight": w, "limit": self.max_single_name},
                        requires_action=True,
                        suggested_action=f"Trim {ticker} to below {self.max_single_name}%",
                    )
                )
        return alerts

    def _check_volatility_spikes(
        self,
        run_id: str,
        current: dict[str, float],
        reference: dict[str, float],
        atr_data: dict[str, float],
    ) -> list[MonitoringAlert]:
        alerts: list[MonitoringAlert] = []
        for ticker, atr in atr_data.items():
            if ticker not in current or ticker not in reference:
                continue
            daily_move = abs(current[ticker] - reference[ticker])
            if atr > 0 and daily_move > atr * self.atr_multiplier:
                alerts.append(
                    MonitoringAlert(
                        alert_id=self._next_alert_id(run_id),
                        run_id=run_id,
                        alert_type=AlertType.VOLATILITY_SPIKE,
                        severity=AlertSeverity.WARNING,
                        ticker=ticker,
                        headline=f"{ticker} moved {daily_move / atr:.1f}× ATR — volatility spike",
                        details={
                            "daily_move": round(daily_move, 2),
                            "atr": round(atr, 2),
                            "atr_multiple": round(daily_move / atr, 2),
                        },
                    )
                )
        return alerts
