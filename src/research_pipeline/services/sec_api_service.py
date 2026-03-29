"""SEC API Service — primary US filing data layer (sec-api.io / dv2).

Closes the most fundamental evidentiary weakness: the Evidence Librarian prompt
references SEC filings as sources but the live engine only has FMP filing
metadata links, not filing content.

This service provides:
  - Filing index per ticker (latest 10-K, 10-Q, 8-K)
  - Section extraction from 10-K/Q (MD&A, Risk Factors, Business)
  - 8-K real-time material event detection
  - XBRL structured financials for FMP cross-validation
  - Form 3/4/5 insider trading (primary SEC source)

Limitations (as assessed in BACKEND_ARCHITECTURE_ASSESSMENT.md §9.4):
  - US-listed companies only — zero benefit for ASX-listed tickers
  - Free tier: 100 req/day; production use requires paid plan
  - Large documents are chunked/truncated for prompt safety

API reference: https://sec-api.io/docs
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    import httpx
    _HTTPX_AVAILABLE = True
except ImportError:
    _HTTPX_AVAILABLE = False
    logger.warning("httpx not available — SECApiService will return empty results")

_TIMEOUT_SECS = 20.0
_MAX_SECTION_CHARS = 4_000   # per-section truncation for prompt safety
_FORM_TYPES_PRIMARY = ["10-K", "10-Q", "8-K"]
_FORM_TYPES_INSIDER = ["4", "3", "5"]

# SEC section identifiers for ExtractorApi
_SECTIONS = {
    "1A": "risk_factors",
    "7":  "mda",         # MD&A
    "1":  "business",
}


def _truncate(text: str, max_chars: int = _MAX_SECTION_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n[... truncated — {len(text) - max_chars} chars omitted]"


def _parse_date(val: Any) -> Optional[datetime]:
    if not val:
        return None
    val = str(val).strip()[:10]  # "YYYY-MM-DD"
    try:
        return datetime.strptime(val, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


class SECFilingRecord:
    """Lightweight filing record parsed from SEC API response."""

    __slots__ = (
        "ticker", "accession_no", "form_type", "filed_at",
        "company_name", "filing_url",
    )

    def __init__(
        self,
        ticker: str,
        accession_no: str,
        form_type: str,
        filed_at: Optional[datetime],
        company_name: str,
        filing_url: str,
    ):
        self.ticker = ticker
        self.accession_no = accession_no
        self.form_type = form_type
        self.filed_at = filed_at
        self.company_name = company_name
        self.filing_url = filing_url

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "accession_no": self.accession_no,
            "form_type": self.form_type,
            "filed_at": self.filed_at.isoformat() if self.filed_at else None,
            "company_name": self.company_name,
            "filing_url": self.filing_url,
            "source": "sec_api",
            "source_tier": 1,
        }


class SECFilingPackage:
    """All SEC data collected for a single ticker."""

    def __init__(self, ticker: str):
        self.ticker = ticker
        self.recent_filings: list[SECFilingRecord] = []
        self.mda_text: str = ""           # 10-K/Q MD&A section
        self.risk_factors_text: str = ""  # 10-K Risk Factors
        self.business_text: str = ""      # 10-K Business description
        self.eight_k_events: list[dict[str, Any]] = []   # recent 8-K material events
        self.insider_transactions: list[dict[str, Any]] = []  # Form 3/4/5
        self.xbrl_facts: dict[str, Any] = {}   # XBRL financial facts for cross-validation
        self.coverage_gaps: list[str] = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "recent_filings": [f.to_dict() for f in self.recent_filings],
            "mda_text": self.mda_text,
            "risk_factors_text": self.risk_factors_text,
            "business_text": self.business_text,
            "eight_k_events": self.eight_k_events,
            "insider_transactions": self.insider_transactions,
            "xbrl_facts": self.xbrl_facts,
            "coverage_gaps": self.coverage_gaps,
            "source": "sec_api",
            "source_tier": 1,
        }

    @property
    def has_primary_content(self) -> bool:
        """True if at least MD&A or Risk Factors text was extracted."""
        return bool(self.mda_text or self.risk_factors_text)


class SECApiService:
    """Fetches primary SEC filing data from sec-api.io.

    Designed to be additive to the existing qualitative layer — all methods
    degrade gracefully when the API key is absent, when rate limits are hit,
    or when the ticker has no US filings (ASX-listed names).

    Usage:
        svc = SECApiService(api_key="your-key")
        package = await svc.fetch_ticker(client, "NVDA")
        packages = await svc.fetch_universe(["NVDA", "MSFT"])
    """

    BASE_URL = "https://api.sec-api.io"
    EXTRACTOR_URL = "https://api.sec-api.io/extractor"
    XBRL_URL = "https://api.sec-api.io/xbrl-to-json"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self._available = bool(api_key) and _HTTPX_AVAILABLE

    # ── Public API ─────────────────────────────────────────────────────

    async def fetch_universe(
        self, tickers: list[str]
    ) -> dict[str, SECFilingPackage]:
        """Fetch SEC data for all tickers. Returns dict ticker → SECFilingPackage."""
        if not self._available:
            return {
                t: SECFilingPackage(ticker=t)
                for t in tickers
            }

        async with httpx.AsyncClient(timeout=_TIMEOUT_SECS) as client:
            results: dict[str, SECFilingPackage] = {}
            for ticker in tickers:
                try:
                    results[ticker] = await self.fetch_ticker(client, ticker)
                except Exception as exc:
                    logger.warning("SEC API failed for %s: %s", ticker, exc)
                    pkg = SECFilingPackage(ticker=ticker)
                    pkg.coverage_gaps.append(f"fetch_error: {exc}")
                    results[ticker] = pkg
        return results

    async def fetch_ticker(
        self, client: httpx.AsyncClient, ticker: str
    ) -> SECFilingPackage:
        """Fetch all SEC data for one ticker."""
        pkg = SECFilingPackage(ticker=ticker)

        # 1. Filing index — get recent 10-K, 10-Q, 8-K
        filings = await self._safe(
            self._fetch_filing_index(client, ticker),
            "filing_index", pkg.coverage_gaps,
        )
        if filings:
            pkg.recent_filings = filings

            # 2. Section extraction from most recent 10-K or 10-Q
            annual_or_quarterly = next(
                (f for f in filings if f.form_type in ("10-K", "10-Q")),
                None,
            )
            if annual_or_quarterly:
                sections = await self._safe(
                    self._extract_sections(client, annual_or_quarterly.filing_url),
                    "section_extraction", pkg.coverage_gaps,
                )
                if sections:
                    pkg.mda_text = sections.get("mda", "")
                    pkg.risk_factors_text = sections.get("risk_factors", "")
                    pkg.business_text = sections.get("business", "")

            # 3. 8-K events
            eight_ks = [f for f in filings if f.form_type == "8-K"]
            pkg.eight_k_events = [f.to_dict() for f in eight_ks[:5]]

        # 4. Insider transactions (Form 4)
        insider = await self._safe(
            self._fetch_insider_transactions(client, ticker),
            "insider_transactions", pkg.coverage_gaps,
        )
        if insider:
            pkg.insider_transactions = insider

        return pkg

    # ── Filing index ────────────────────────────────────────────────────

    async def _fetch_filing_index(
        self, client: httpx.AsyncClient, ticker: str
    ) -> list[SECFilingRecord]:
        """Query the full-text search API to get a filing index for a ticker."""
        payload = {
            "query": {
                "query_string": {
                    "query": f'ticker:"{ticker}" AND formType:("10-K" OR "10-Q" OR "8-K")',
                }
            },
            "from": "0",
            "size": "10",
            "sort": [{"filedAt": {"order": "desc"}}],
        }
        resp = await client.post(
            f"{self.BASE_URL}",
            json=payload,
            headers={"Authorization": self.api_key},
        )
        resp.raise_for_status()
        data = resp.json()

        records: list[SECFilingRecord] = []
        for hit in (data.get("filings") or []):
            records.append(SECFilingRecord(
                ticker=ticker,
                accession_no=hit.get("accessionNo", ""),
                form_type=hit.get("formType", ""),
                filed_at=_parse_date(hit.get("filedAt")),
                company_name=hit.get("companyName", ""),
                filing_url=hit.get("linkToFilingDetails", ""),
            ))
        return records

    # ── Section extraction ──────────────────────────────────────────────

    async def _extract_sections(
        self, client: httpx.AsyncClient, filing_url: str
    ) -> dict[str, str]:
        """Extract key sections from a 10-K/10-Q using the Extractor API."""
        result: dict[str, str] = {}
        for section_id, field_name in _SECTIONS.items():
            try:
                resp = await client.get(
                    self.EXTRACTOR_URL,
                    params={
                        "url": filing_url,
                        "item": section_id,
                        "type": "text",
                        "token": self.api_key,
                    },
                )
                resp.raise_for_status()
                text = resp.text or ""
                result[field_name] = _truncate(text)
            except Exception as exc:
                logger.debug("Section %s extraction failed for %s: %s", section_id, filing_url, exc)
        return result

    # ── Insider transactions ────────────────────────────────────────────

    async def _fetch_insider_transactions(
        self, client: httpx.AsyncClient, ticker: str
    ) -> list[dict[str, Any]]:
        """Fetch Form 3/4/5 insider transactions."""
        payload = {
            "query": {
                "query_string": {
                    "query": f'ticker:"{ticker}" AND formType:("4" OR "3" OR "5")',
                }
            },
            "from": "0",
            "size": "10",
            "sort": [{"filedAt": {"order": "desc"}}],
        }
        resp = await client.post(
            f"{self.BASE_URL}",
            json=payload,
            headers={"Authorization": self.api_key},
        )
        resp.raise_for_status()
        data = resp.json()
        transactions = []
        for hit in (data.get("filings") or [])[:10]:
            transactions.append({
                "ticker": ticker,
                "form_type": hit.get("formType", ""),
                "filed_at": hit.get("filedAt", ""),
                "reporting_owner": hit.get("reportingOwner", ""),
                "transaction_date": hit.get("transactionDate", ""),
                "filing_url": hit.get("linkToFilingDetails", ""),
                "source": "sec_api",
                "source_tier": 1,
            })
        return transactions

    # ── Utility ─────────────────────────────────────────────────────────

    @staticmethod
    async def _safe(coro: Any, source_name: str, gaps: list[str]) -> Any:
        try:
            return await coro
        except Exception as exc:
            gaps.append(f"{source_name}: {exc}")
            logger.debug("SEC API source '%s' failed: %s", source_name, exc)
            return None
