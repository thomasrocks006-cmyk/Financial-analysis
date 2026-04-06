"""Universe Configuration.

Defines the stock/ETF universes the pipeline can operate on.
New universes can be added without touching engine.py — just add an entry
to the appropriate constant and it is automatically picked up.

The default discovery mode starts from BROAD_MARKET_UNIVERSE, which spans
equities, ETFs, fixed income, commodities, and alternatives.  The pre-built
thematic presets (AI infrastructure, global tech, etc.) remain available as
a "side option" when the user explicitly selects a preset universe.
"""

from __future__ import annotations

from typing import Final

# ── Equity Sector Universes ───────────────────────────────────────────────────

AI_INFRASTRUCTURE_UNIVERSE: Final[list[str]] = [
    # AI chip designers & foundries
    "NVDA",
    "AMD",
    "INTC",
    "AVGO",
    "MRVL",
    "QCOM",
    "ON",
    # Cloud hyper-scalers with AI buildout
    "MSFT",
    "GOOGL",
    "AMZN",
    "META",
    "AAPL",
    # AI-native software / platforms
    "PLTR",
    "AI",
    "SNOW",
    "MDB",
    "DDOG",
    "GTLB",
    # Data centre REITs & infrastructure
    "EQIX",
    "DLR",
    "AMT",
    # AI hardware adjacencies & networking
    "ARM",
    "TSM",
    "ANET",
    "SMCI",
    "VRT",
    "DELL",
    # Power & cooling infrastructure
    "VST",
    "CEG",
    "NEE",
]

GLOBAL_TECH_UNIVERSE: Final[list[str]] = AI_INFRASTRUCTURE_UNIVERSE + [
    # Enterprise SaaS
    "ORCL",
    "CRM",
    "NOW",
    "WDAY",
    "SAP",
    "ADBE",
    "INTU",
    # Semis & EDA tooling
    "ASML",
    "KLAC",
    "AMAT",
    "LRCX",
    "TXN",
    "MCHP",
    # Networking / security
    "CSCO",
    "PANW",
    "CRWD",
    "FTNT",
    # Consumer tech
    "SPOT",
    "NFLX",
    # Energy transition
    "AES",
    "BEP",
    "ENPH",
]

HEALTHCARE_UNIVERSE: Final[list[str]] = [
    # Large-cap pharma
    "JNJ",
    "PFE",
    "MRK",
    "ABBV",
    "LLY",
    "NVO",
    "AZN",
    # Biotech
    "AMGN",
    "GILD",
    "BIIB",
    "REGN",
    "VRTX",
    # Medical devices
    "MDT",
    "ABT",
    "SYK",
    "ISRG",
    "EW",
    # Healthcare services / managed care
    "UNH",
    "CVS",
    "HCA",
    "CI",
    # Healthcare ETFs
    "XLV",
    "IBB",
    "VHT",
]

FINANCIALS_UNIVERSE: Final[list[str]] = [
    # US mega-cap banks
    "JPM",
    "BAC",
    "WFC",
    "C",
    "GS",
    "MS",
    # Insurance
    "BRK-B",
    "AIG",
    "MET",
    "PRU",
    "AFL",
    # Fintech
    "V",
    "MA",
    "AXP",
    "PYPL",
    "SQ",
    "NU",
    # Asset managers
    "BLK",
    "SCHW",
    "IVZ",
    # Financial ETFs
    "XLF",
    "KBE",
    "KRE",
]

CONSUMER_UNIVERSE: Final[list[str]] = [
    # Consumer staples
    "PG",
    "KO",
    "PEP",
    "WMT",
    "COST",
    "MDLZ",
    "CL",
    # Consumer discretionary
    "AMZN",
    "TSLA",
    "HD",
    "NKE",
    "SBUX",
    "MCD",
    "LOW",
    "TGT",
    "BKNG",
    # Consumer ETFs
    "XLP",
    "XLY",
    "VCR",
]

ENERGY_MATERIALS_UNIVERSE: Final[list[str]] = [
    # Oil & gas majors
    "XOM",
    "CVX",
    "COP",
    "SLB",
    "EOG",
    "PXD",
    "OXY",
    # Renewables
    "NEE",
    "CEG",
    "AES",
    "ENPH",
    "FSLR",
    "RUN",
    # Mining & materials
    "FCX",
    "NEM",
    "BHP",
    "RIO",
    "AA",
    "X",
    # Energy / Materials ETFs
    "XLE",
    "XLB",
    "GDX",
    "USO",
    "UNG",
]

REAL_ESTATE_UNIVERSE: Final[list[str]] = [
    # Diversified REITs
    "VNQ",
    "IYR",
    # Data centre REITs
    "EQIX",
    "DLR",
    "AMT",
    "CCI",
    # Industrial / logistics REITs
    "PLD",
    "REXR",
    "EGP",
    # Residential REITs
    "AVB",
    "EQR",
    "INVH",
    # Office / retail REITs
    "SPG",
    "BXP",
    "O",
]

# ── Fixed Income ──────────────────────────────────────────────────────────────

FIXED_INCOME_UNIVERSE: Final[list[str]] = [
    # US Treasuries — short to long duration
    "SHV",
    "SGOV",
    "BIL",
    "SHY",
    "IEI",
    "IEF",
    "TLH",
    "TLT",
    "EDV",
    # Investment-grade corporate credit
    "LQD",
    "VCIT",
    "VCLT",
    "IGIB",
    # High yield
    "HYG",
    "JNK",
    "SHYG",
    "USHY",
    # Inflation-linked
    "TIP",
    "STIP",
    "SCHP",
    # International sovereign
    "BNDX",
    "EMB",
    "PCY",
    # Municipal bonds
    "MUB",
    "VTEB",
    # Floating rate / ultra-short
    "FLOT",
    "USFR",
]

# ── Commodities ───────────────────────────────────────────────────────────────

COMMODITY_UNIVERSE: Final[list[str]] = [
    # Precious metals
    "GLD",
    "IAU",
    "SLV",
    "PPLT",
    "PALL",
    # Base metals & mining
    "DBB",
    "COPX",
    # Energy commodities
    "USO",
    "UNG",
    "PDBC",
    "DJP",
    # Agriculture
    "DBA",
    "CORN",
    "WEAT",
    # Broad commodities
    "GSG",
    "PDBC",
]

# ── Alternatives ──────────────────────────────────────────────────────────────

ALTERNATIVES_UNIVERSE: Final[list[str]] = [
    # Crypto ETFs / proxies
    "IBIT",
    "FBTC",
    "ETHA",
    "GBTC",
    # Volatility products
    "VIXY",
    "UVXY",
    # Managed futures / trend
    "DBMF",
    "KMLM",
    "CTA",
    # Merger arbitrage
    "MNA",
    # Multi-alternative
    "QAI",
    "BTAL",
    # Infrastructure
    "IFRA",
    "IGF",
    # Private equity proxies
    "PSP",
    "LBO",
]

# ── ETF Benchmarks & Broad Market ────────────────────────────────────────────

ETF_BENCHMARK_UNIVERSE: Final[list[str]] = [
    # US broad market
    "SPY",
    "VOO",
    "IVV",
    "QQQ",
    "IWM",
    "VTI",
    "DIA",
    # International developed
    "EFA",
    "VEA",
    "IEFA",
    # Emerging markets
    "EEM",
    "VWO",
    "IEMG",
    # Sector ETFs
    "XLK",
    "XLF",
    "XLV",
    "XLE",
    "XLY",
    "XLP",
    "XLI",
    "XLB",
    "XLU",
    "XLRE",
    # AI / tech themes
    "BOTZ",
    "AIQ",
    "SOXX",
    "ROBO",
    "WCLD",
    # Factor ETFs
    "MTUM",
    "VLUE",
    "QUAL",
    "USMV",
]

# ── BROAD MARKET UNIVERSE (Default Discovery Starting Point) ──────────────────
# This is the default starting universe for the "discovery" / "live research"
# mode.  It spans all major asset classes so the pipeline can rank and filter
# candidates across the full investment opportunity set.

BROAD_MARKET_UNIVERSE: Final[list[str]] = [
    # ── US Large-cap equities — core sectors ──
    # Technology
    "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "AVGO", "AMD", "ORCL", "CRM",
    # AI / Semiconductors
    "ARM", "TSM", "ANET", "INTC", "MRVL", "QCOM", "NOW", "PLTR", "AI", "SNOW",
    # Healthcare
    "LLY", "UNH", "JNJ", "ABBV", "MRK", "PFE", "NVO", "AMGN", "GILD", "MDT",
    # Financials
    "JPM", "BAC", "GS", "MS", "BRK-B", "V", "MA", "BLK", "SCHW", "AXP",
    # Consumer
    "TSLA", "WMT", "COST", "HD", "MCD", "KO", "PEP", "PG", "NKE", "SBUX",
    # Energy & Materials
    "XOM", "CVX", "COP", "NEE", "CEG", "FCX", "NEM", "SLB", "EOG", "OXY",
    # Industrials
    "CAT", "HON", "UNP", "BA", "RTX", "LMT", "GE", "MMM", "DE", "FDX",
    # Real estate & Infrastructure
    "EQIX", "DLR", "AMT", "PLD", "O", "CCI",
    # ── International equities ──
    "SAP", "AZN", "ASML", "TM", "BABA", "TCEHY",
    # ── ETFs — broad market & sector ──
    "SPY", "QQQ", "IWM", "EFA", "EEM", "VTI",
    "XLK", "XLF", "XLV", "XLE", "XLY", "XLI", "XLRE",
    "SOXX", "BOTZ", "AIQ",
    # ── Fixed income ETFs ──
    "TLT", "IEF", "SHV", "LQD", "HYG", "TIP", "BNDX", "EMB", "AGG", "BND",
    # ── Commodities ──
    "GLD", "SLV", "USO", "UNG", "DBA", "PDBC",
    # ── Alternatives ──
    "IBIT", "FBTC", "DBMF", "KMLM", "VNQ", "IGF",
]

# ── Thematic Sub-groups ───────────────────────────────────────────────────────

_SUBTHEME_MAP: Final[dict[str, dict[str, list[str]]]] = {
    "ai_infrastructure": {
        "ai_chips": ["NVDA", "AMD", "AVGO", "MRVL", "QCOM", "ON"],
        "foundries": ["INTC", "TSM"],
        "hyperscalers": ["MSFT", "GOOGL", "AMZN", "META", "AAPL"],
        "ai_software": ["PLTR", "AI", "SNOW", "MDB", "DDOG", "GTLB"],
        "data_centres": ["EQIX", "DLR", "AMT"],
        "networking": ["ANET", "SMCI", "VRT", "DELL"],
        "power_energy": ["VST", "CEG", "NEE"],
    },
    "global_tech": {
        "enterprise_software": ["ORCL", "CRM", "NOW", "WDAY", "SAP", "ADBE", "INTU"],
        "eda_materials": ["ASML", "KLAC", "AMAT", "LRCX"],
        "semis_broad": ["QCOM", "TXN", "INTC", "MCHP"],
        "networking_security": ["ANET", "CSCO", "PANW", "CRWD", "FTNT"],
        "energy_transition": ["NEE", "AES", "BEP", "ENPH"],
    },
    "fixed_income": {
        "government_short": ["SHV", "SGOV", "BIL", "SHY"],
        "government_long": ["IEF", "TLH", "TLT", "EDV"],
        "investment_grade": ["LQD", "VCIT", "VCLT", "IGIB"],
        "high_yield": ["HYG", "JNK", "SHYG", "USHY"],
        "inflation_linked": ["TIP", "STIP", "SCHP"],
        "international": ["BNDX", "EMB", "PCY"],
        "municipal": ["MUB", "VTEB"],
    },
    "healthcare": {
        "large_pharma": ["JNJ", "PFE", "MRK", "ABBV", "LLY", "NVO", "AZN"],
        "biotech": ["AMGN", "GILD", "BIIB", "REGN", "VRTX"],
        "medical_devices": ["MDT", "ABT", "SYK", "ISRG", "EW"],
        "managed_care": ["UNH", "CVS", "HCA", "CI"],
    },
    "financials": {
        "banks": ["JPM", "BAC", "WFC", "C", "GS", "MS"],
        "insurance": ["BRK-B", "AIG", "MET", "PRU", "AFL"],
        "fintech": ["V", "MA", "AXP", "PYPL", "SQ", "NU"],
        "asset_managers": ["BLK", "SCHW", "IVZ"],
    },
    "broad_market": {
        "us_equities": ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN"],
        "ai_semis": ["ARM", "TSM", "ANET", "INTC", "MRVL", "QCOM"],
        "healthcare": ["LLY", "UNH", "JNJ", "ABBV", "MRK"],
        "financials": ["JPM", "BAC", "GS", "V", "MA", "BLK"],
        "consumer": ["TSLA", "WMT", "COST", "HD", "MCD"],
        "energy": ["XOM", "CVX", "NEE", "CEG"],
        "industrials": ["CAT", "HON", "UNP", "BA"],
        "etfs": ["SPY", "QQQ", "IWM", "EFA", "EEM"],
        "fixed_income": ["TLT", "IEF", "LQD", "HYG", "TIP", "AGG"],
        "commodities": ["GLD", "SLV", "USO", "PDBC"],
        "alternatives": ["IBIT", "FBTC", "DBMF", "VNQ"],
    },
}

# ── Accessor API ──────────────────────────────────────────────────────────────

_UNIVERSE_REGISTRY: Final[dict[str, list[str]]] = {
    "broad_market": BROAD_MARKET_UNIVERSE,
    "ai_infrastructure": AI_INFRASTRUCTURE_UNIVERSE,
    "global_tech": GLOBAL_TECH_UNIVERSE,
    "healthcare": HEALTHCARE_UNIVERSE,
    "financials": FINANCIALS_UNIVERSE,
    "consumer": CONSUMER_UNIVERSE,
    "energy_materials": ENERGY_MATERIALS_UNIVERSE,
    "real_estate": REAL_ESTATE_UNIVERSE,
    "fixed_income": FIXED_INCOME_UNIVERSE,
    "commodities": COMMODITY_UNIVERSE,
    "alternatives": ALTERNATIVES_UNIVERSE,
    "etf_benchmarks": ETF_BENCHMARK_UNIVERSE,
}

# Human-readable labels and descriptions for each universe preset
UNIVERSE_METADATA: Final[dict[str, dict[str, str]]] = {
    "broad_market": {
        "label": "Broad Market Discovery",
        "description": (
            "Full cross-asset universe spanning US and international equities across all sectors, "
            "ETFs, fixed income, commodities, and alternatives. Default starting point for live research."
        ),
        "asset_classes": "Equities, ETFs, Fixed Income, Commodities, Alternatives",
    },
    "ai_infrastructure": {
        "label": "AI Infrastructure",
        "description": (
            "AI chip designers, foundries, cloud hyperscalers, AI-native software platforms, "
            "data centre REITs, networking, and power/cooling infrastructure."
        ),
        "asset_classes": "Equities, REITs",
    },
    "global_tech": {
        "label": "Global Technology",
        "description": (
            "Broad technology universe including AI infrastructure plus enterprise SaaS, "
            "EDA tooling, cybersecurity, and energy transition."
        ),
        "asset_classes": "Equities",
    },
    "healthcare": {
        "label": "Healthcare & Biotech",
        "description": (
            "Large-cap pharma, biotech innovators, medical device makers, and managed care operators, "
            "plus sector ETFs."
        ),
        "asset_classes": "Equities, ETFs",
    },
    "financials": {
        "label": "Financials & Fintech",
        "description": (
            "US mega-cap banks, insurance, fintech payment networks, and asset managers."
        ),
        "asset_classes": "Equities, ETFs",
    },
    "consumer": {
        "label": "Consumer (Staples & Discretionary)",
        "description": (
            "Consumer staples and discretionary names spanning retail, food & beverage, "
            "e-commerce, EVs, and apparel."
        ),
        "asset_classes": "Equities, ETFs",
    },
    "energy_materials": {
        "label": "Energy, Materials & Renewables",
        "description": (
            "Oil & gas majors, renewables, mining and materials companies, plus commodity ETFs."
        ),
        "asset_classes": "Equities, ETFs, Commodities",
    },
    "real_estate": {
        "label": "Real Estate (REITs)",
        "description": (
            "Diversified, data-centre, industrial, residential, and office REITs plus REIT ETFs."
        ),
        "asset_classes": "REITs, ETFs",
    },
    "fixed_income": {
        "label": "Fixed Income",
        "description": (
            "US Treasuries (short to long duration), investment-grade and high-yield credit, "
            "inflation-linked bonds, international sovereign, and municipal bond ETFs."
        ),
        "asset_classes": "Bond ETFs",
    },
    "commodities": {
        "label": "Commodities",
        "description": (
            "Precious metals, base metals, energy commodities, agriculture, and broad commodity ETFs."
        ),
        "asset_classes": "Commodity ETFs",
    },
    "alternatives": {
        "label": "Alternatives",
        "description": (
            "Crypto ETFs, volatility products, managed futures, merger arbitrage, infrastructure, "
            "and private equity proxy ETFs."
        ),
        "asset_classes": "Alternative ETFs",
    },
    "etf_benchmarks": {
        "label": "ETF Benchmarks",
        "description": (
            "Broad market, international, sector, and factor ETFs used as benchmarks and for "
            "thematic exposure without single-stock risk."
        ),
        "asset_classes": "ETFs",
    },
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


def get_universe_metadata(name: str) -> dict[str, str]:
    """Return human-readable label, description, and asset classes for a universe.

    Returns an empty dict if no metadata is registered.
    """
    return dict(UNIVERSE_METADATA.get(name, {}))


def list_universe_details() -> list[dict[str, str | int]]:
    """Return a list of all registered universes with metadata and ticker counts."""
    result = []
    for key, tickers in _UNIVERSE_REGISTRY.items():
        meta = UNIVERSE_METADATA.get(key, {})
        result.append(
            {
                "id": key,
                "label": meta.get("label", key.replace("_", " ").title()),
                "description": meta.get("description", ""),
                "asset_classes": meta.get("asset_classes", ""),
                "ticker_count": len(tickers),
            }
        )
    return result
