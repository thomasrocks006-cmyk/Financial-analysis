"""Test fixtures and shared configuration."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure src is on path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture
def sample_tickers() -> list[str]:
    return ["NVDA", "AVGO", "TSM", "CEG", "VST", "GEV", "PWR", "ETN", "APH"]


@pytest.fixture
def sample_market_snapshot() -> dict:
    """Matches MarketSnapshot schema exactly."""
    return {
        "ticker": "NVDA",
        "price": 125.50,
        "market_cap": 3.08e12,
        "trailing_pe": 55.2,
        "forward_pe": 32.1,
        "dividend_yield": 0.02,
        "revenue_ttm": 1.13e11,
        "net_income_ttm": 6.3e10,
        "source": "fmp",
    }


@pytest.fixture
def sample_claim() -> dict:
    """Matches the actual Claim Pydantic model."""
    return {
        "claim_id": "CLM-NVDA-001",
        "run_id": "RUN-TEST-001",
        "ticker": "NVDA",
        "claim_text": "NVIDIA data-centre revenue grew 409% YoY to $18.4B in Q4 FY2024",
        "evidence_class": "primary_fact",
        "source_id": "SRC-10K-NVDA-2024",
        "source_url": "https://sec.gov/nvda-10k",
        "confidence": "high",
        "status": "pass",
        "owner_agent": "sector_compute",
    }


@pytest.fixture
def sample_portfolio_positions() -> list[dict]:
    return [
        {
            "ticker": "NVDA",
            "weight_pct": 12.0,
            "subtheme": "compute",
            "entry_quality": "strong",
            "thesis_integrity": "robust",
        },
        {
            "ticker": "AVGO",
            "weight_pct": 10.0,
            "subtheme": "compute",
            "entry_quality": "strong",
            "thesis_integrity": "robust",
        },
        {
            "ticker": "TSM",
            "weight_pct": 8.0,
            "subtheme": "compute",
            "entry_quality": "acceptable",
            "thesis_integrity": "moderate",
        },
        {
            "ticker": "CEG",
            "weight_pct": 10.0,
            "subtheme": "power",
            "entry_quality": "strong",
            "thesis_integrity": "robust",
        },
        {
            "ticker": "VST",
            "weight_pct": 8.0,
            "subtheme": "power",
            "entry_quality": "acceptable",
            "thesis_integrity": "moderate",
        },
        {
            "ticker": "GEV",
            "weight_pct": 7.0,
            "subtheme": "power",
            "entry_quality": "acceptable",
            "thesis_integrity": "moderate",
        },
        {
            "ticker": "PWR",
            "weight_pct": 10.0,
            "subtheme": "infrastructure",
            "entry_quality": "strong",
            "thesis_integrity": "robust",
        },
        {
            "ticker": "ETN",
            "weight_pct": 9.0,
            "subtheme": "infrastructure",
            "entry_quality": "acceptable",
            "thesis_integrity": "moderate",
        },
        {
            "ticker": "APH",
            "weight_pct": 8.0,
            "subtheme": "infrastructure",
            "entry_quality": "acceptable",
            "thesis_integrity": "moderate",
        },
        {
            "ticker": "FCX",
            "weight_pct": 6.0,
            "subtheme": "materials",
            "entry_quality": "acceptable",
            "thesis_integrity": "moderate",
        },
        {
            "ticker": "BHP",
            "weight_pct": 6.0,
            "subtheme": "materials",
            "entry_quality": "acceptable",
            "thesis_integrity": "moderate",
        },
        {
            "ticker": "NXT",
            "weight_pct": 6.0,
            "subtheme": "infrastructure",
            "entry_quality": "acceptable",
            "thesis_integrity": "moderate",
        },
    ]
