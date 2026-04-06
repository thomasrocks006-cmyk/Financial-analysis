"""Global settings derived from environment and config files."""

from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class APIKeys:
    """External API credentials loaded from environment."""

    fmp_api_key: str = ""
    finnhub_api_key: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""  # optional — only needed if using OpenAI models
    google_api_key: str = ""  # optional — only needed if using Google Gemini models
    # Session 19 / DSQ-2+3: new primary and finance-event API keys
    sec_api_key: str = ""      # sec-api.io — Tier 1 primary US filings
    benzinga_api_key: str = "" # Benzinga — Tier 2 finance-native news + ratings
    # GDR-1: Gemini Deep Research (Stage 4.5) — separate from google_api_key
    gemini_api_key: str = ""   # GEMINI_API_KEY — used only by GeminiDeepResearchService

    @classmethod
    def from_env(cls) -> "APIKeys":
        return cls(
            fmp_api_key=os.getenv("FMP_API_KEY", ""),
            finnhub_api_key=os.getenv("FINNHUB_API_KEY", ""),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            google_api_key=os.getenv("GOOGLE_API_KEY", ""),
            sec_api_key=os.getenv("SEC_API_KEY", ""),
            benzinga_api_key=os.getenv("BENZINGA_API_KEY", ""),
            gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        )

    def validate(self) -> list[str]:
        """Return list of missing required keys.

        At least one LLM key (Anthropic, OpenAI, or Google) is required.
        FMP and Finnhub are required for data ingestion.
        """
        missing = []
        if not self.fmp_api_key:
            missing.append("FMP_API_KEY")
        if not self.finnhub_api_key:
            missing.append("FINNHUB_API_KEY")
        if not (self.anthropic_api_key or self.openai_api_key or self.google_api_key):
            missing.append(
                "ANTHROPIC_API_KEY or OPENAI_API_KEY or GOOGLE_API_KEY (at least one LLM key required)"
            )
        return missing


@dataclass
class Settings:
    """Top-level application settings."""

    project_root: Path = field(default_factory=lambda: Path(__file__).resolve().parents[3])
    config_dir: Path = field(default=None)
    storage_dir: Path = field(default=None)
    reports_dir: Path = field(default=None)
    prompts_dir: Path = field(default=None)
    db_url: str = "sqlite:///storage/registry.db"
    # Default to Claude Sonnet; override via env or caller.
    # base_agent.py routes to Anthropic if model starts with "claude",
    # to OpenAI otherwise — so this default must match the available key.
    llm_model: str = "claude-sonnet-4-6"
    llm_temperature: float = 0.2
    max_retries: int = 3
    api_keys: APIKeys = field(default_factory=APIKeys.from_env)

    def __post_init__(self):
        if self.config_dir is None:
            self.config_dir = self.project_root / "configs"
        if self.storage_dir is None:
            self.storage_dir = self.project_root / "storage"
        if self.reports_dir is None:
            self.reports_dir = self.project_root / "reports"
        if self.prompts_dir is None:
            self.prompts_dir = self.project_root / "prompts"

        # Ensure directories exist
        for d in [
            self.storage_dir,
            self.reports_dir,
            self.storage_dir / "raw",
            self.storage_dir / "processed",
            self.storage_dir / "artifacts",
        ]:
            d.mkdir(parents=True, exist_ok=True)
