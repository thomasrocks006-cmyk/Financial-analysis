"""ESG Service — ESG scoring, exclusion management, and ESG mandate compliance."""

from __future__ import annotations

import logging
from typing import Any

from research_pipeline.schemas.governance import ESGConfig, ESGRating, ESGScore

logger = logging.getLogger(__name__)


# ── Default ESG profiles per AI Infrastructure ticker ──────────────────────

# Heuristic ESG scores based on public reporting profiles for AI infra tickers.
# Real implementation would pull from MSCI, Sustainalytics, or ISS.
_DEFAULT_ESG_SCORES: dict[str, dict[str, Any]] = {
    "NVDA": {"overall": "AA", "e": 6.5, "s": 7.0, "g": 8.0, "controversy": False},
    "AMD": {"overall": "A", "e": 6.0, "s": 6.5, "g": 7.5, "controversy": False},
    "AVGO": {"overall": "A", "e": 5.5, "s": 6.0, "g": 7.0, "controversy": False},
    "MRVL": {"overall": "BBB", "e": 5.0, "s": 5.5, "g": 6.5, "controversy": False},
    "ARM": {"overall": "A", "e": 6.0, "s": 7.0, "g": 7.5, "controversy": False},
    "TSM": {"overall": "AA", "e": 7.0, "s": 6.5, "g": 7.0, "controversy": False},
    "MSFT": {"overall": "AAA", "e": 8.5, "s": 8.0, "g": 9.0, "controversy": False},
    "AMZN": {"overall": "A", "e": 6.0, "s": 5.5, "g": 7.0, "controversy": False},
    "GOOGL": {"overall": "AA", "e": 7.5, "s": 7.0, "g": 7.5, "controversy": False},
    "META": {"overall": "BBB", "e": 5.5, "s": 4.5, "g": 6.0, "controversy": True},
    "EQIX": {"overall": "AA", "e": 7.5, "s": 6.5, "g": 8.0, "controversy": False},
    "DLR": {"overall": "A", "e": 7.0, "s": 6.0, "g": 7.5, "controversy": False},
    "VRT": {"overall": "BBB", "e": 5.5, "s": 5.5, "g": 6.0, "controversy": False},
    "DELL": {"overall": "A", "e": 6.0, "s": 6.0, "g": 7.0, "controversy": False},
    "SMCI": {"overall": "BB", "e": 4.0, "s": 4.5, "g": 4.0, "controversy": True},
}


class ESGService:
    """ESG scoring and exclusion management — no LLM.

    Provides ESG scores per ticker, checks exclusion lists, and validates
    portfolio compliance against ESG mandates.
    """

    def __init__(self, config: ESGConfig | None = None):
        self.config = config or ESGConfig()
        self._scores_cache: dict[str, ESGScore] = {}

    def get_score(self, ticker: str) -> ESGScore:
        """Get ESG score for a ticker — cached after first lookup."""
        if ticker in self._scores_cache:
            return self._scores_cache[ticker]

        profile = _DEFAULT_ESG_SCORES.get(ticker)
        if profile:
            score = ESGScore(
                ticker=ticker,
                overall_rating=ESGRating(profile["overall"]),
                environmental_score=profile["e"],
                social_score=profile["s"],
                governance_score=profile["g"],
                controversy_flag=profile["controversy"],
                excluded=ticker in self.config.exclusion_list,
                source="heuristic_profiles",
            )
        else:
            # Unknown ticker — assign neutral BBB
            score = ESGScore(
                ticker=ticker,
                overall_rating=ESGRating.BBB,
                environmental_score=5.0,
                social_score=5.0,
                governance_score=5.0,
                source="default_unknown",
            )

        self._scores_cache[ticker] = score
        return score

    def get_portfolio_scores(self, tickers: list[str]) -> list[ESGScore]:
        """Get ESG scores for all portfolio tickers."""
        return [self.get_score(t) for t in tickers]

    def check_exclusion(self, ticker: str) -> tuple[bool, str]:
        """Check if a ticker is excluded under the current ESG mandate.

        Returns (is_excluded, reason).
        """
        score = self.get_score(ticker)

        # Hard exclusion list
        if ticker in self.config.exclusion_list:
            return True, f"{ticker} is on the explicit exclusion list"

        # Rating below threshold
        rating_order = list(ESGRating)
        ticker_idx = rating_order.index(score.overall_rating)
        threshold_idx = rating_order.index(self.config.exclude_below_rating)
        if ticker_idx > threshold_idx:  # higher index = worse rating
            return True, f"{ticker} ESG rating {score.overall_rating.value} below threshold {self.config.exclude_below_rating.value}"

        # Controversy flag
        if self.config.exclude_controversial and score.controversy_flag:
            return True, f"{ticker} flagged for ESG controversy"

        # Minimum composite score
        composite = (score.environmental_score + score.social_score + score.governance_score) / 3
        if composite < self.config.min_esg_score:
            return True, f"{ticker} composite ESG score {composite:.1f} below minimum {self.config.min_esg_score}"

        return False, ""

    def check_portfolio_esg_compliance(
        self,
        tickers: list[str],
        weights: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """Full ESG compliance check for a portfolio.

        Returns a dict with per-ticker results and overall compliance status.
        """
        results: dict[str, Any] = {
            "compliant": True,
            "excluded_tickers": [],
            "warnings": [],
            "scores": {},
        }

        for ticker in tickers:
            excluded, reason = self.check_exclusion(ticker)
            score = self.get_score(ticker)
            results["scores"][ticker] = {
                "rating": score.overall_rating.value,
                "environmental": score.environmental_score,
                "social": score.social_score,
                "governance": score.governance_score,
                "controversy": score.controversy_flag,
            }

            if excluded:
                results["compliant"] = False
                results["excluded_tickers"].append({"ticker": ticker, "reason": reason})

            # Soft warnings for borderline cases
            composite = (score.environmental_score + score.social_score + score.governance_score) / 3
            if not excluded and composite < self.config.min_esg_score + 1.0:
                results["warnings"].append(
                    f"{ticker} ESG composite {composite:.1f} is within 1.0 of limit ({self.config.min_esg_score})"
                )

        # Portfolio-level weighted ESG score (if weights provided)
        if weights:
            weighted_e = sum(self.get_score(t).environmental_score * weights.get(t, 0) / 100 for t in tickers)
            weighted_s = sum(self.get_score(t).social_score * weights.get(t, 0) / 100 for t in tickers)
            weighted_g = sum(self.get_score(t).governance_score * weights.get(t, 0) / 100 for t in tickers)
            results["portfolio_weighted_esg"] = {
                "environmental": round(weighted_e, 2),
                "social": round(weighted_s, 2),
                "governance": round(weighted_g, 2),
                "composite": round((weighted_e + weighted_s + weighted_g) / 3, 2),
            }

        return results

    def portfolio_esg_summary(self, tickers: list[str]) -> str:
        """Generate a text summary of portfolio ESG profile."""
        scores = self.get_portfolio_scores(tickers)
        lines = ["ESG Portfolio Summary", "=" * 40]

        for s in scores:
            flag = " ⚠ CONTROVERSY" if s.controversy_flag else ""
            composite = (s.environmental_score + s.social_score + s.governance_score) / 3
            lines.append(
                f"{s.ticker:6s}  {s.overall_rating.value:3s}  E={s.environmental_score:.1f}  "
                f"S={s.social_score:.1f}  G={s.governance_score:.1f}  "
                f"Composite={composite:.1f}{flag}"
            )

        return "\n".join(lines)
