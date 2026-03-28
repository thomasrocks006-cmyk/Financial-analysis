"""Client onboarding and investment profile system.

Emulates JPMorgan Asset Management's client profiling process for
high-net-worth individuals. Captures:
  - Investment objectives (growth, income, preservation, total return)
  - Risk tolerance (conservative, moderate, aggressive)
  - Time horizon
  - Sector preferences / exclusions
  - ESG / ethical constraints
  - Liquidity needs
  - Existing portfolio positions
  - Tax considerations

The profile drives all downstream pipeline decisions:
  - Universe selection (which tickers to analyse)
  - Portfolio construction constraints
  - Risk tolerance thresholds
  - Report tone and recommendations style
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ── Investment Themes ─────────────────────────────────────────────────────

INVESTMENT_THEMES = {
    "ai_infrastructure": {
        "name": "AI Infrastructure & Compute",
        "description": "Full AI stack: semiconductors, power generation, grid infrastructure, cooling, materials",
        "default_tickers": [
            "NVDA",
            "AVGO",
            "TSM",
            "CEG",
            "VST",
            "GEV",
            "PWR",
            "ETN",
            "APH",
            "FIX",
            "FCX",
            "NXT",
        ],
        "sectors": ["Technology", "Energy", "Industrials", "Materials"],
    },
    "tech_mega": {
        "name": "Technology Mega-Caps",
        "description": "Dominant tech platforms and cloud hyperscalers",
        "default_tickers": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA"],
        "sectors": ["Technology", "Communication Services", "Consumer Discretionary"],
    },
    "dividend_income": {
        "name": "Dividend Income & Yield",
        "description": "Stable dividend-paying companies across sectors",
        "default_tickers": ["JNJ", "PG", "KO", "PEP", "MCD", "VZ", "IBM", "MMM", "XOM", "CVX"],
        "sectors": ["Healthcare", "Consumer Staples", "Energy", "Industrials"],
    },
    "growth_innovation": {
        "name": "Growth & Innovation",
        "description": "High-growth companies in emerging technology sectors",
        "default_tickers": [
            "NVDA",
            "TSLA",
            "CRM",
            "SNOW",
            "PLTR",
            "NET",
            "CRWD",
            "DDOG",
            "MDB",
            "COIN",
        ],
        "sectors": ["Technology", "Communication Services", "Financials"],
    },
    "defensive_value": {
        "name": "Defensive Value",
        "description": "Undervalued, cash-generative companies with strong moats",
        "default_tickers": ["BRK-B", "JPM", "UNH", "JNJ", "PG", "WMT", "HD", "LMT", "RTX", "GD"],
        "sectors": ["Financials", "Healthcare", "Consumer Staples", "Industrials"],
    },
    "clean_energy": {
        "name": "Clean Energy & Sustainability",
        "description": "Renewable energy, EV infrastructure, ESG leaders",
        "default_tickers": [
            "NEE",
            "ENPH",
            "FSLR",
            "CEG",
            "VST",
            "GEV",
            "NXT",
            "PLUG",
            "BE",
            "SEDG",
        ],
        "sectors": ["Energy", "Industrials", "Technology"],
    },
    "custom": {
        "name": "Custom Universe",
        "description": "Client selects specific tickers for analysis",
        "default_tickers": [],
        "sectors": [],
    },
}


# ── Risk Profiles ────────────────────────────────────────────────────────

RISK_PROFILES = {
    "conservative": {
        "label": "Conservative",
        "description": "Capital preservation priority. Low volatility, high income, defensive positioning.",
        "max_single_position_pct": 8,
        "max_sector_pct": 30,
        "min_positions": 12,
        "max_beta": 0.9,
        "preferred_quality": "high",
        "volatility_tolerance": "low",
        "drawdown_tolerance_pct": 10,
    },
    "moderate": {
        "label": "Moderate",
        "description": "Balanced growth and income. Diversified across sectors and styles.",
        "max_single_position_pct": 12,
        "max_sector_pct": 35,
        "min_positions": 8,
        "max_beta": 1.2,
        "preferred_quality": "medium",
        "volatility_tolerance": "medium",
        "drawdown_tolerance_pct": 20,
    },
    "aggressive": {
        "label": "Aggressive Growth",
        "description": "Maximum capital appreciation. Higher concentration, growth-oriented, higher volatility acceptable.",
        "max_single_position_pct": 15,
        "max_sector_pct": 45,
        "min_positions": 5,
        "max_beta": 2.0,
        "preferred_quality": "any",
        "volatility_tolerance": "high",
        "drawdown_tolerance_pct": 35,
    },
}


@dataclass
class ClientProfile:
    """Represents a high-net-worth client's investment profile."""

    # Identity
    name: str = "Client"

    # Investment objectives
    primary_objective: str = "total_return"  # growth | income | preservation | total_return
    investment_theme: str = "ai_infrastructure"
    time_horizon_years: int = 5

    # Risk
    risk_tolerance: str = "moderate"  # conservative | moderate | aggressive

    # Universe
    tickers: list[str] = field(default_factory=list)
    custom_tickers: list[str] = field(default_factory=list)
    excluded_tickers: list[str] = field(default_factory=list)
    sector_preferences: list[str] = field(default_factory=list)
    sector_exclusions: list[str] = field(default_factory=list)

    # Constraints
    esg_mandate: bool = False
    exclude_tobacco: bool = False
    exclude_weapons: bool = False
    exclude_fossil_fuel: bool = False
    min_market_cap_bn: float = 5.0  # minimum market cap filter

    # Portfolio
    target_portfolio_size: int = 10
    target_dividend_yield_pct: float = 0.0  # 0 = no requirement
    max_single_position_pct: float = 12.0
    benchmark: str = "SPY"  # SPY | QQQ | IWM | custom

    # Investment amount
    investment_amount_usd: float = 1_000_000.0

    # Notes
    special_instructions: str = ""

    def get_risk_profile(self) -> dict:
        """Get the risk profile parameters for this client."""
        return RISK_PROFILES.get(self.risk_tolerance, RISK_PROFILES["moderate"])

    def get_theme_info(self) -> dict:
        """Get the investment theme details."""
        return INVESTMENT_THEMES.get(self.investment_theme, INVESTMENT_THEMES["custom"])

    def get_effective_tickers(self) -> list[str]:
        """Get the final ticker universe after applying all filters."""
        if self.tickers:
            base = list(self.tickers)
        elif self.custom_tickers:
            base = list(self.custom_tickers)
        else:
            theme = self.get_theme_info()
            base = list(theme.get("default_tickers", []))

        # Remove exclusions
        base = [t for t in base if t not in self.excluded_tickers]

        return base

    def get_portfolio_constraints(self) -> dict:
        """Get portfolio construction constraints based on profile."""
        risk = self.get_risk_profile()
        return {
            "max_single_position_pct": min(
                self.max_single_position_pct, risk["max_single_position_pct"]
            ),
            "max_sector_pct": risk["max_sector_pct"],
            "min_positions": risk["min_positions"],
            "max_beta": risk["max_beta"],
            "target_positions": self.target_portfolio_size,
            "volatility_tolerance": risk["volatility_tolerance"],
            "drawdown_tolerance_pct": risk["drawdown_tolerance_pct"],
            "benchmark": self.benchmark,
            "esg_mandate": self.esg_mandate,
            "time_horizon_years": self.time_horizon_years,
            "primary_objective": self.primary_objective,
            "investment_amount_usd": self.investment_amount_usd,
        }

    def to_prompt_context(self) -> str:
        """Generate a structured context block for LLM prompts.

        This is injected into every agent's system prompt so they tailor
        their analysis to this specific client's profile and needs.
        """
        risk = self.get_risk_profile()
        theme = self.get_theme_info()
        constraints = self.get_portfolio_constraints()

        obj_labels = {
            "growth": "Capital Growth — maximise total return through price appreciation",
            "income": "Income Generation — prioritise dividend yield and stable cash flows",
            "preservation": "Capital Preservation — minimise downside risk, protect principal",
            "total_return": "Total Return — balanced approach to growth and income",
        }

        exclusions = []
        if self.esg_mandate:
            exclusions.append("ESG mandate active — exclude companies with ESG controversies")
        if self.exclude_tobacco:
            exclusions.append("Exclude tobacco companies")
        if self.exclude_weapons:
            exclusions.append("Exclude controversial weapons manufacturers")
        if self.exclude_fossil_fuel:
            exclusions.append("Exclude pure-play fossil fuel extraction")
        if self.sector_exclusions:
            exclusions.append(f"Excluded sectors: {', '.join(self.sector_exclusions)}")

        return f"""
═══ CLIENT INVESTMENT PROFILE ═══
Client: {self.name}
Date: Generated for current analysis run

PRIMARY OBJECTIVE: {obj_labels.get(self.primary_objective, self.primary_objective)}
INVESTMENT THEME: {theme["name"]} — {theme["description"]}
RISK TOLERANCE: {risk["label"]} — {risk["description"]}
TIME HORIZON: {self.time_horizon_years} years
INVESTMENT AMOUNT: ${self.investment_amount_usd:,.0f}

PORTFOLIO CONSTRAINTS:
  • Max single position: {constraints["max_single_position_pct"]}%
  • Max sector concentration: {constraints["max_sector_pct"]}%
  • Min positions: {constraints["min_positions"]}
  • Target positions: {constraints["target_positions"]}
  • Max portfolio beta: {constraints["max_beta"]}
  • Drawdown tolerance: {constraints["drawdown_tolerance_pct"]}%
  • Benchmark: {self.benchmark}
  • Min market cap: ${self.min_market_cap_bn}B

MANDATE RESTRICTIONS:
{chr(10).join(f"  • {e}" for e in exclusions) if exclusions else "  • No specific restrictions"}

{f"SPECIAL INSTRUCTIONS: {self.special_instructions}" if self.special_instructions else ""}
══════════════════════════════════
""".strip()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for storage."""
        return {
            "name": self.name,
            "primary_objective": self.primary_objective,
            "investment_theme": self.investment_theme,
            "time_horizon_years": self.time_horizon_years,
            "risk_tolerance": self.risk_tolerance,
            "tickers": self.tickers,
            "custom_tickers": self.custom_tickers,
            "excluded_tickers": self.excluded_tickers,
            "sector_preferences": self.sector_preferences,
            "sector_exclusions": self.sector_exclusions,
            "esg_mandate": self.esg_mandate,
            "exclude_tobacco": self.exclude_tobacco,
            "exclude_weapons": self.exclude_weapons,
            "exclude_fossil_fuel": self.exclude_fossil_fuel,
            "min_market_cap_bn": self.min_market_cap_bn,
            "target_portfolio_size": self.target_portfolio_size,
            "target_dividend_yield_pct": self.target_dividend_yield_pct,
            "max_single_position_pct": self.max_single_position_pct,
            "benchmark": self.benchmark,
            "investment_amount_usd": self.investment_amount_usd,
            "special_instructions": self.special_instructions,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ClientProfile":
        """Deserialize from dict."""
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
