"""Phase 7.6 — Universe Configuration.

Defines the stock/ETF universes the pipeline can operate on.
New universes can be added without touching engine.py — just add an entry
to the appropriate constant and it is automatically picked up.
"""

from __future__ import annotations

from typing import Final

# ── Universe Definitions ──────────────────────────────────────────────────────

AI_INFRASTRUCTURE_UNIVERSE: Final[list[str]] = [
    # AI chip designers & foundries
    "NVDA",
    "AMD",
    "INTC",
    "AVGO",
    "MRVL",
    # Cloud hyper-scalers with AI buildout
    "MSFT",
    "GOOGL",
    "AMZN",
    "META",
    # AI-native software / platforms
    "PLTR",
    "AI",
    "SNOW",
    "MDB",
    # Power & cooling infrastructure
    "VST",
]

GLOBAL_TECH_UNIVERSE: Final[list[str]] = AI_INFRASTRUCTURE_UNIVERSE + [
    # Expanded hyperscalers + pure-play cloud
    "ORCL",
    "CRM",
    "NOW",
    "WDAY",
    # Semis & EDA tooling
    "QCOM",
    "TXN",
    "ASML",
    "KLAC",
    "AMAT",
    "LRCX",
    # Networking
    "ANET",
    "CSCO",
    # AI hardware adjacencies
    "ARM",
    "TSM",
    # Energy for AI data centres
    "NEE",
    "AES",
    "CEG",
]

FIXED_INCOME_UNIVERSE: Final[list[str]] = [
    # US Treasuries
    "TLT",
    "IEF",
    "SHV",
    "SGOV",
    # Investment-grade credit
    "LQD",
    "VCIT",
    # High yield
    "HYG",
    "JNK",
    # Inflation-linked
    "TIP",
    "TIPS",
    # International sovereign
    "BNDX",
]

COMMODITY_UNIVERSE: Final[list[str]] = [
    "GLD",
    "SLV",
    "PDBC",
    "USO",
    "UNG",
]

ETF_BENCHMARK_UNIVERSE: Final[list[str]] = [
    "SPY",
    "QQQ",
    "IWM",
    "EFA",
    "EEM",
    "BOTZ",
    "AIQ",
    "SOXX",
    "XLK",
    "ROBO",
]

# ── Thematic Sub-groups ───────────────────────────────────────────────────────

_SUBTHEME_MAP: Final[dict[str, dict[str, list[str]]]] = {
    "ai_infrastructure": {
        "ai_chips": ["NVDA", "AMD", "AVGO", "MRVL"],
        "foundries": ["INTC", "TSM"],
        "hyperscalers": ["MSFT", "GOOGL", "AMZN", "META"],
        "ai_software": ["PLTR", "AI", "SNOW", "MDB"],
        "power_energy": ["VST"],
    },
    "global_tech": {
        "enterprise_software": ["ORCL", "CRM", "NOW", "WDAY"],
        "eda_materials": ["ASML", "KLAC", "AMAT", "LRCX"],
        "semis_broad": ["QCOM", "TXN", "INTC"],
        "networking": ["ANET", "CSCO"],
        "energy_transition": ["NEE", "AES", "CEG"],
    },
    "fixed_income": {
        "government": ["TLT", "IEF", "SHV", "SGOV"],
        "investment_grade": ["LQD", "VCIT"],
        "high_yield": ["HYG", "JNK"],
        "inflation_linked": ["TIP"],
        "international": ["BNDX"],
    },
}

# ── Accessor API ──────────────────────────────────────────────────────────────

_UNIVERSE_REGISTRY: Final[dict[str, list[str]]] = {
    "ai_infrastructure": AI_INFRASTRUCTURE_UNIVERSE,
    "global_tech": GLOBAL_TECH_UNIVERSE,
    "fixed_income": FIXED_INCOME_UNIVERSE,
    "commodities": COMMODITY_UNIVERSE,
    "etf_benchmarks": ETF_BENCHMARK_UNIVERSE,
}


def get_universe(name: str) -> list[str]:
    """Return the ticker list for universe *name*.

    Raises:
        KeyError: if the universe name is not registered.
    """
    if name not in _UNIVERSE_REGISTRY:
        raise KeyError(f"Unknown universe '{name}'. Available: {list(_UNIVERSE_REGISTRY)}")
    return list(_UNIVERSE_REGISTRY[name])


def list_universes() -> list[str]:
    """Return the names of all registered universes."""
    return list(_UNIVERSE_REGISTRY)


def get_subtheme_map(universe_name: str) -> dict[str, list[str]]:
    """Return {subtheme: [tickers]} for a universe.

    Returns an empty dict if no sub-theme map is defined.
    """
    return dict(_SUBTHEME_MAP.get(universe_name, {}))


def get_subtheme(universe_name: str, subtheme: str) -> list[str]:
    """Return tickers for a specific sub-theme within a universe.

    Raises:
        KeyError: if the subtheme is not defined.
    """
    universe_themes = _SUBTHEME_MAP.get(universe_name, {})
    if subtheme not in universe_themes:
        raise KeyError(
            f"Unknown subtheme '{subtheme}' in universe '{universe_name}'. "
            f"Available: {list(universe_themes)}"
        )
    return list(universe_themes[subtheme])


def ticker_to_subtheme(ticker: str, universe_name: str) -> str | None:
    """Map a ticker to its sub-theme label within a universe, or None."""
    for theme, tickers in _SUBTHEME_MAP.get(universe_name, {}).items():
        if ticker in tickers:
            return theme
    return None
