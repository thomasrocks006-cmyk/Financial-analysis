"""Demo market data for pipeline test runs (no FMP/Finnhub API required).

All figures are illustrative estimates as of March 2026 based on
publicly available information. They are NOT live data.
"""

from __future__ import annotations
from datetime import date

DEMO_DATE = "2026-03-24"

# ── Universe ──────────────────────────────────────────────────────────────
FULL_UNIVERSE = {
    "compute": ["NVDA", "AVGO", "TSM"],
    "power_energy": ["CEG", "VST", "GEV"],
    "infrastructure": ["PWR", "ETN", "APH", "FIX", "FCX", "NXT"],
}

QUICK_DEMO_UNIVERSE = {
    "compute": ["NVDA"],
    "power_energy": ["CEG"],
    "infrastructure": ["PWR"],
}

# ── Market snapshots (illustrative, March 2026) ─────────────────────────
MARKET_SNAPSHOTS: dict[str, dict] = {
    "NVDA": {
        "ticker": "NVDA",
        "company_name": "NVIDIA Corporation",
        "subtheme": "compute",
        "price": 108.50,
        "market_cap_bn": 2650,
        "revenue_ttm_bn": 130,
        "revenue_next_yr_consensus_bn": 175,
        "gross_margin_pct": 74.5,
        "forward_pe": 35.2,
        "ev_ebitda": 28.4,
        "consensus_target_12m": 155.0,
        "analyst_ratings": {"buy": 42, "hold": 8, "sell": 2},
        "debt_to_equity": 0.35,
        "free_cash_flow_ttm_bn": 62,
        "recent_catalysts": [
            "Blackwell GB200 NVL72 systems shipping at scale Q1 2026",
            "Data centre revenue guidance raised to $170B+ for FY2027",
            "CUDA ecosystem lock-in deepening; Hopper→Blackwell→Vera Rubin roadmap confirmed",
            "DeepSeek-R2 efficiency gains raised debate on training compute intensity",
            "Custom silicon (Google TPU v7, Amazon Trainium 3) gaining traction at margin",
        ],
        "key_risks": [
            "AI spending plateau if hyperscaler ROI disappoints",
            "DeepSeek-style efficiency gains reducing per-query training compute",
            "Custom ASIC displacement risk at Google/Meta/Amazon (15-20% market share risk)",
            "Taiwan geopolitical risk (TSM concentration)",
            "Export control escalation on H20/B20 to China",
        ],
        "data_freshness": "Q4 FY2026 earnings (Feb 2026)",
        "data_tier": "Tier 3 consensus — illustrative demo data",
    },
    "AVGO": {
        "ticker": "AVGO",
        "company_name": "Broadcom Inc.",
        "subtheme": "compute",
        "price": 192.40,
        "market_cap_bn": 892,
        "revenue_ttm_bn": 58,
        "revenue_next_yr_consensus_bn": 68,
        "gross_margin_pct": 64.1,
        "forward_pe": 28.5,
        "ev_ebitda": 22.1,
        "consensus_target_12m": 225.0,
        "analyst_ratings": {"buy": 28, "hold": 7, "sell": 1},
        "debt_to_equity": 1.8,
        "free_cash_flow_ttm_bn": 22,
        "recent_catalysts": [
            "Custom AI ASIC business (XPUs for Google/Meta/Apple) tracking $12B+ FY2026",
            "VMware integration delivering higher-than-expected cross-sell",
            "AI networking (Jericho3-AI) seeing strong hyperscaler demand",
            "Q1 FY2026 beat driven by semiconductor solutions segment",
        ],
        "key_risks": [
            "Customer concentration: Google/Meta/Apple = majority of XPU revenue",
            "NVDA custom silicon pivot could slow hyperscaler XPU adoption",
            "VMware churn if customers migrate to open-source alternatives",
            "High leverage post-VMware acquisition limits buyback capacity",
        ],
        "data_freshness": "Q1 FY2026 earnings (Mar 2026)",
        "data_tier": "Tier 3 consensus — illustrative demo data",
    },
    "TSM": {
        "ticker": "TSM",
        "company_name": "Taiwan Semiconductor Manufacturing",
        "subtheme": "compute",
        "price": 192.00,
        "market_cap_bn": 995,
        "revenue_ttm_bn": 86,
        "revenue_next_yr_consensus_bn": 105,
        "gross_margin_pct": 56.1,
        "forward_pe": 26.8,
        "ev_ebitda": 18.5,
        "consensus_target_12m": 220.0,
        "analyst_ratings": {"buy": 33, "hold": 5, "sell": 1},
        "debt_to_equity": 0.28,
        "free_cash_flow_ttm_bn": 28,
        "recent_catalysts": [
            "N2 (2nm) ramp ahead of schedule; NVDA Vera Rubin and AMD Zen 6 on N2",
            "CoWoS packaging capacity expansion: 35k wafers/month by end-2026",
            "Arizona fab (Fab 21) Phase 2 construction underway; $65B US commitment",
            "AI chip demand accelerating CoWoS allocation to 40%+ of advanced packaging revenue",
        ],
        "key_risks": [
            "Cross-strait tension — existential geopolitical risk; hard to hedge",
            "Customer concentration: Apple + NVDA + AMD = >60% revenue",
            "US restrictions on advanced node exports to China",
            "Pricing pressure on N3 as yield matures and Samsung/Intel compete",
            "Arizona ramp cost headwinds suppressing margin 2-3 years",
        ],
        "data_freshness": "Q4 2025 earnings (Jan 2026)",
        "data_tier": "Tier 3 consensus — illustrative demo data",
    },
    "CEG": {
        "ticker": "CEG",
        "company_name": "Constellation Energy Corporation",
        "subtheme": "power_energy",
        "price": 310.20,
        "market_cap_bn": 99,
        "revenue_ttm_bn": 24,
        "revenue_next_yr_consensus_bn": 26,
        "gross_margin_pct": 38.2,
        "forward_pe": 38.4,
        "ev_ebitda": 22.3,
        "consensus_target_12m": 368.0,
        "analyst_ratings": {"buy": 18, "hold": 5, "sell": 2},
        "debt_to_equity": 1.2,
        "free_cash_flow_ttm_bn": 3.4,
        "recent_catalysts": [
            "Three Mile Island Unit 1 restart (Crane Clean Energy Center) supplying Microsoft under 20yr PPA",
            "Calpine acquisition announced Dec 2024 — transforms to largest US clean energy producer",
            "Additional nuclear PPA negotiations ongoing with hyperscalers (AWS, Google)",
            "IRA nuclear PTC ($15/MWh) provides revenue floor through 2032",
            "Data centre power demand driving 24/7 carbon-free energy premium valuations",
        ],
        "key_risks": [
            "Regulatory risk: NRC licence extensions, state nuclear policy",
            "Calpine integration complexity; gas fleet adds carbon exposure",
            "Premium valuation pricing in perfect execution on nuclear restarts",
            "Power price normalisation if gas generation capacity surges",
            "Single-name hyperscaler concentration in PPA book",
        ],
        "data_freshness": "Q4 2025 earnings (Feb 2026)",
        "data_tier": "Tier 3 consensus — illustrative demo data",
    },
    "VST": {
        "ticker": "VST",
        "company_name": "Vistra Corp",
        "subtheme": "power_energy",
        "price": 165.80,
        "market_cap_bn": 52,
        "revenue_ttm_bn": 17,
        "revenue_next_yr_consensus_bn": 19,
        "gross_margin_pct": 42.5,
        "forward_pe": 22.1,
        "ev_ebitda": 14.8,
        "consensus_target_12m": 188.0,
        "analyst_ratings": {"buy": 14, "hold": 6, "sell": 2},
        "debt_to_equity": 2.4,
        "free_cash_flow_ttm_bn": 2.8,
        "recent_catalysts": [
            "Energy Harbor nuclear fleet acquisition adding 4GW zero-carbon baseload",
            "Texas ERCOT market tightening supports power price upside",
            "Data centre collocation development agreements (Ohio, Texas)",
            "Significant share buyback programme underway",
        ],
        "key_risks": [
            "Higher leverage than peers; less financial flexibility vs CEG",
            "ERCOT merchant exposure — unhedged tail risk in heat/cold events",
            "Gas fleet carbon liability as IRA enforcement tightens",
            "Regulatory risk on nuclear PTC eligibility for acquired fleet",
        ],
        "data_freshness": "Q4 2025 earnings (Feb 2026)",
        "data_tier": "Tier 3 consensus — illustrative demo data",
    },
    "GEV": {
        "ticker": "GEV",
        "company_name": "GE Vernova",
        "subtheme": "power_energy",
        "price": 398.60,
        "market_cap_bn": 108,
        "revenue_ttm_bn": 36,
        "revenue_next_yr_consensus_bn": 40,
        "gross_margin_pct": 16.8,
        "forward_pe": 52.4,
        "ev_ebitda": 31.2,
        "consensus_target_12m": 440.0,
        "analyst_ratings": {"buy": 20, "hold": 8, "sell": 1},
        "debt_to_equity": 0.45,
        "free_cash_flow_ttm_bn": 1.8,
        "recent_catalysts": [
            "Gas turbine backlog at record $70B+ driven by data centre power demand",
            "Grid solutions segment orders up 40% YoY — transformer lead times 4-5 years",
            "Wind segment restructuring improving margins; offshore strategic review",
            "CEO signalled higher margin targets; 2028 guidance raised",
        ],
        "key_risks": [
            "Execution risk on large gas turbine backlog — supply chain bottlenecks",
            "Wind segment losses burning cash; offshore disposal timeline uncertain",
            "Premium multiple requires sustained margin improvement",
            "Transformer/grid equipment competition from Siemens Energy, ABB, Hitachi",
        ],
        "data_freshness": "Q4 2025 earnings (Feb 2026)",
        "data_tier": "Tier 3 consensus — illustrative demo data",
    },
    "PWR": {
        "ticker": "PWR",
        "company_name": "Quanta Services",
        "subtheme": "infrastructure",
        "price": 342.80,
        "market_cap_bn": 47,
        "revenue_ttm_bn": 22,
        "revenue_next_yr_consensus_bn": 26,
        "gross_margin_pct": 14.8,
        "forward_pe": 34.5,
        "ev_ebitda": 20.1,
        "consensus_target_12m": 388.0,
        "analyst_ratings": {"buy": 22, "hold": 4, "sell": 0},
        "debt_to_equity": 0.72,
        "free_cash_flow_ttm_bn": 1.6,
        "recent_catalysts": [
            "Grid modernisation spending accelerating — FERC Order 1920 compliance backlog",
            "Data centre electrical infrastructure contracts (HV connections, substations)",
            "Renewable grid interconnection queue at record depth; PWR is primary contractor",
            "Acquired Cupertino Electric — specialist data centre power contractor",
            "12-month backlog +18% YoY to $35B",
        ],
        "key_risks": [
            "Labour and skilled trades scarcity limiting peak throughput",
            "Permitting delays on major transmission projects",
            "Weather and project execution risk — fixed-price contract exposure",
            "Customer concentration in utility sector if capex cycles turn",
        ],
        "data_freshness": "Q4 2025 earnings (Feb 2026)",
        "data_tier": "Tier 3 consensus — illustrative demo data",
    },
    "ETN": {
        "ticker": "ETN",
        "company_name": "Eaton Corporation",
        "subtheme": "infrastructure",
        "price": 385.20,
        "market_cap_bn": 155,
        "revenue_ttm_bn": 24,
        "revenue_next_yr_consensus_bn": 27,
        "gross_margin_pct": 38.6,
        "forward_pe": 32.8,
        "ev_ebitda": 24.5,
        "consensus_target_12m": 432.0,
        "analyst_ratings": {"buy": 26, "hold": 6, "sell": 1},
        "debt_to_equity": 0.58,
        "free_cash_flow_ttm_bn": 3.2,
        "recent_catalysts": [
            "Data centre power management (UPS, PDUs, switchgear) = 25% of revenue and fastest growth",
            "Electrical segment orders +22% YoY — transformer and switchgear lead times elevated",
            "Aerospace segment benefiting from commercial aero recovery",
            "AI infrastructure buildout driving double-digit electrical segment growth",
        ],
        "key_risks": [
            "Supply chain for transformers/switchgear; silicon steel and copper constraints",
            "Premium valuation if electrical segment growth moderates post buildout peak",
            "Geopolitical risk on manufacturing footprint (Mexico, EMEA)",
        ],
        "data_freshness": "Q4 2025 earnings (Feb 2026)",
        "data_tier": "Tier 3 consensus — illustrative demo data",
    },
    "APH": {
        "ticker": "APH",
        "company_name": "Amphenol Corporation",
        "subtheme": "infrastructure",
        "price": 72.40,
        "market_cap_bn": 110,
        "revenue_ttm_bn": 15,
        "revenue_next_yr_consensus_bn": 18,
        "gross_margin_pct": 33.2,
        "forward_pe": 38.1,
        "ev_ebitda": 27.4,
        "consensus_target_12m": 85.0,
        "analyst_ratings": {"buy": 20, "hold": 7, "sell": 0},
        "debt_to_equity": 0.52,
        "free_cash_flow_ttm_bn": 2.1,
        "recent_catalysts": [
            "AI/data centre interconnect and high-speed connector demand surge",
            "Backplane and optical transceiver connectors for 400G/800G/1.6T deployments",
            "Consistent M&A bolt-on strategy; management track record of integration",
        ],
        "key_risks": [
            "High valuation multiple; sensitive to order book normalisation",
            "Competition in data centre connectors from TE Connectivity, Molex",
            "Customer concentration risk if specific hyperscaler capex slows",
        ],
        "data_freshness": "Q4 2025 earnings (Jan 2026)",
        "data_tier": "Tier 3 consensus — illustrative demo data",
    },
    "FIX": {
        "ticker": "FIX",
        "company_name": "Comfort Systems USA",
        "subtheme": "infrastructure",
        "price": 422.10,
        "market_cap_bn": 15,
        "revenue_ttm_bn": 7.2,
        "revenue_next_yr_consensus_bn": 8.8,
        "gross_margin_pct": 18.4,
        "forward_pe": 34.2,
        "ev_ebitda": 22.8,
        "consensus_target_12m": 478.0,
        "analyst_ratings": {"buy": 8, "hold": 3, "sell": 0},
        "debt_to_equity": 0.38,
        "free_cash_flow_ttm_bn": 0.52,
        "recent_catalysts": [
            "Mechanical/HVAC contractor for data centres — AI buildout driving backlog surge",
            "Cooling infrastructure for liquid-cooled AI clusters (direct liquid cooling, CDU)",
            "Backlog up >30% YoY; margins expanding on mix shift to data centre",
        ],
        "key_risks": [
            "Pure-play small cap — liquidity and size constraints",
            "Concentrated in construction sector; execution and labour risks",
            "Backlog monetisation dependent on project completions",
        ],
        "data_freshness": "Q4 2025 earnings (Feb 2026)",
        "data_tier": "Tier 3 consensus — illustrative demo data",
    },
    "FCX": {
        "ticker": "FCX",
        "company_name": "Freeport-McMoRan",
        "subtheme": "infrastructure",
        "price": 38.20,
        "market_cap_bn": 55,
        "revenue_ttm_bn": 24,
        "revenue_next_yr_consensus_bn": 26,
        "gross_margin_pct": 34.8,
        "forward_pe": 19.4,
        "ev_ebitda": 8.2,
        "consensus_target_12m": 48.0,
        "analyst_ratings": {"buy": 18, "hold": 10, "sell": 2},
        "debt_to_equity": 0.62,
        "free_cash_flow_ttm_bn": 3.4,
        "recent_catalysts": [
            "Copper demand thesis: AI data centre + grid buildout = structural demand supercycle",
            "Global copper deficit projected 2026-2030 as new mine supply constrained (20yr permitting)",
            "Grasberg mine (Indonesia) sustaining high-grade production",
            "Molybdenum production uplift as energy transition drives stainless steel demand",
        ],
        "key_risks": [
            "Copper price volatility — commodity risk not equity risk",
            "Chinese demand slowdown remains biggest swing factor",
            "Indonesia sovereign risk; operating in 80% Grasberg PTFI structure",
            "Mine permitting timelines for US development pipeline",
        ],
        "data_freshness": "Q4 2025 earnings (Feb 2026)",
        "data_tier": "Tier 3 consensus — illustrative demo data",
    },
    "NXT": {
        "ticker": "NXT",
        "company_name": "Nextracker Inc.",
        "subtheme": "infrastructure",
        "price": 42.80,
        "market_cap_bn": 7.8,
        "revenue_ttm_bn": 2.6,
        "revenue_next_yr_consensus_bn": 3.2,
        "gross_margin_pct": 22.1,
        "forward_pe": 24.8,
        "ev_ebitda": 16.5,
        "consensus_target_12m": 55.0,
        "analyst_ratings": {"buy": 12, "hold": 4, "sell": 1},
        "debt_to_equity": 0.42,
        "free_cash_flow_ttm_bn": 0.38,
        "recent_catalysts": [
            "Solar tracker leader; utility-scale solar co-located with AI data centres",
            "IRA Section 45X manufacturing credits extending visibility",
            "Record backlog driven by large-scale solar + storage RFPs from hyperscalers",
        ],
        "key_risks": [
            "Tariff risk on steel/aluminium inputs",
            "Solar policy uncertainty under current administration",
            "Competition from Array Technologies, GameChange Solar",
        ],
        "data_freshness": "Q4 FY2025 earnings (Jan 2026)",
        "data_tier": "Tier 3 consensus — illustrative demo data",
    },
}


def get_sector_snapshot(sector: str, tickers: list[str] | None = None) -> dict:
    """Return a structured market data package for a sector."""
    sector_map = FULL_UNIVERSE
    if tickers is None:
        tickers = sum(sector_map.values(), [])

    return {
        "date": DEMO_DATE,
        "data_source": "Demo data — illustrative only. Not live prices.",
        "stocks": {t: MARKET_SNAPSHOTS[t] for t in tickers if t in MARKET_SNAPSHOTS},
    }


def get_macro_context() -> dict:
    """Return a macro / regime context package for demo runs."""
    return {
        "date": DEMO_DATE,
        "regime": "Late cycle expansion — AI capex supercycle underway",
        "fed_funds_rate": 4.25,
        "us_10yr_yield": 4.45,
        "ust_2s10s_spread_bp": 32,
        "vix": 18.4,
        "dxy": 103.8,
        "copper_usd_lb": 4.62,
        "brent_crude_usd": 74.50,
        "natural_gas_usd_mmbtu": 3.85,
        "uranium_spot_usd_lb": 88.0,
        "key_themes": [
            "AI infrastructure capex: hyperscalers guiding $250B+ combined 2026 capex",
            "Power scarcity: data centre power demand is primary grid stress since 2025",
            "Interest rate environment: Fed on hold; 2 cuts expected H2 2026",
            "Geopolitical: US-China tech controls tightening; Taiwan risk elevated",
            "Dollar: stable-strong; commodity risk partially offset",
        ],
        "regime_assessment": (
            "Risk-on environment with selective positioning. "
            "AI infrastructure theme has broad institutional ownership. "
            "Power/energy sub-theme less crowded. "
            "Infrastructure & materials remain under-appreciated relative to semiconductor names."
        ),
    }


def get_claim_ledger(tickers: list[str]) -> list[dict]:
    """Generate a minimal illustrative claim ledger for demo tickers."""
    claims = []
    claim_id = 1
    for ticker in tickers:
        snap = MARKET_SNAPSHOTS.get(ticker)
        if not snap:
            continue
        for cat in snap.get("recent_catalysts", []):
            claims.append({
                "claim_id": f"CLM-{ticker}-{claim_id:03d}",
                "ticker": ticker,
                "claim_text": cat,
                "evidence_class": "PRIMARY_FACT",
                "source": snap["data_freshness"],
                "tier": 3,
                "confidence": "medium",
                "status": "pass",
            })
            claim_id += 1
    return claims
