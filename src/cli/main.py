"""CLI interface for the AI Infrastructure Research Pipeline."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table
from rich.panel import Panel

app = typer.Typer(
    name="research-pipeline",
    help="AI Infrastructure Research & Portfolio Platform — v8",
    add_completion=False,
)
console = Console()

# ── Default universe from the skill files ──────────────────────────────
DEFAULT_UNIVERSE = [
    # Compute & Silicon
    "NVDA",
    "AVGO",
    "TSM",
    # Power & Energy
    "CEG",
    "VST",
    "GEV",
    # Infrastructure, Materials & Build-out
    "PWR",
    "ETN",
    "APH",
    "FIX",
    "FCX",
    "BHP",
    "NXT",
]


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(rich_tracebacks=True, show_path=False)],
    )


@app.command()
def run(
    tickers: Optional[str] = typer.Option(
        None,
        "--tickers",
        "-t",
        help="Comma-separated ticker list. Defaults to AI infrastructure universe.",
    ),
    config: Optional[str] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to pipeline YAML config.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging."),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Validate config without executing pipeline."
    ),
):
    """Run the full 15-stage research pipeline."""
    setup_logging(verbose)

    from research_pipeline.config.settings import Settings
    from research_pipeline.config.loader import load_pipeline_config

    settings = Settings()
    pipeline_config = load_pipeline_config(config or settings.config_dir / "pipeline.yaml")

    universe = tickers.split(",") if tickers else DEFAULT_UNIVERSE

    console.print(
        Panel.fit(
            f"[bold blue]AI Infrastructure Research Pipeline v8[/]\n"
            f"Universe: {len(universe)} tickers\n"
            f"Config: {config or 'default'}\n"
            f"Run ID: pending",
            title="Pipeline Startup",
        )
    )

    if dry_run:
        console.print("[yellow]Dry run mode — validating configuration only.[/]")
        _show_universe_table(universe)
        console.print("[green]Configuration valid. Ready to execute.[/]")
        return

    from research_pipeline.pipeline.engine import PipelineEngine

    engine = PipelineEngine(settings, pipeline_config)
    result = asyncio.run(engine.run_full_pipeline(universe))

    # Display results
    if result["status"] == "completed":
        console.print(
            Panel.fit(
                f"[bold green]Pipeline COMPLETED[/]\n"
                f"Run ID: {result['run_id']}\n"
                f"Stages: {len(result.get('stages_completed', []))} completed\n"
                f"Report: {result.get('report_path', 'N/A')}",
                title="Result",
            )
        )
    else:
        console.print(
            Panel.fit(
                f"[bold red]Pipeline FAILED[/]\n"
                f"Run ID: {result.get('run_id', 'N/A')}\n"
                f"Blocked at stage: {result.get('blocked_at', '?')}",
                title="Result",
            )
        )
        raise typer.Exit(1)


@app.command()
def validate(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Config file to validate."),
):
    """Validate pipeline configuration and schemas."""
    setup_logging()
    from research_pipeline.config.settings import Settings
    from research_pipeline.config.loader import load_pipeline_config

    settings = Settings()
    try:
        pipeline_config = load_pipeline_config(config or settings.config_dir / "pipeline.yaml")
        console.print(
            f"[green]Config valid:[/] {pipeline_config.version} — {pipeline_config.project_name}"
        )
        console.print(f"  Stages defined: {len(pipeline_config.stages)}")
        console.print(f"  Portfolio variants: {pipeline_config.portfolio_variants}")
        console.print(f"  Test categories: {pipeline_config.test_categories}")
    except Exception as exc:
        console.print(f"[red]Config invalid:[/] {exc}")
        raise typer.Exit(1)

    # Check API keys
    missing = settings.api_keys.validate()
    if missing:
        console.print(f"[yellow]Missing API keys:[/] {', '.join(missing)}")
    else:
        console.print("[green]All API keys present.[/]")


@app.command()
def test(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Run golden regression tests."""
    setup_logging(verbose)
    from research_pipeline.services.golden_tests import GoldenTestHarness

    harness = GoldenTestHarness()
    results = harness.run_all()

    table = Table(title="Golden Test Results")
    table.add_column("Test ID", style="cyan")
    table.add_column("Category")
    table.add_column("Status")
    table.add_column("Rule")

    for detail in results["details"]:
        status = "[green]PASS[/]" if detail["passed"] else "[red]FAIL[/]"
        table.add_row(detail["test_id"], detail["category"], status, detail["rule"][:60])

    console.print(table)
    console.print(
        f"\n[bold]Total: {results['total']} | Passed: {results['passed']} | Failed: {results['failed']}[/]"
    )


@app.command()
def history(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of recent runs to show."),
):
    """Show recent pipeline run history."""
    setup_logging()
    from research_pipeline.config.settings import Settings
    from research_pipeline.services.run_registry import RunRegistryService

    settings = Settings()
    registry = RunRegistryService(settings.storage_dir)
    runs = registry.list_runs(limit=limit)

    if not runs:
        console.print("[yellow]No runs found.[/]")
        return

    table = Table(title="Pipeline Run History")
    table.add_column("Run ID", style="cyan")
    table.add_column("Status")
    table.add_column("Universe")
    table.add_column("Timestamp")

    for run in runs:
        status_style = "green" if run.status.value == "completed" else "red"
        table.add_row(
            run.run_id[:30],
            f"[{status_style}]{run.status.value}[/]",
            str(len(run.universe)),
            str(run.timestamp)[:19],
        )

    console.print(table)


@app.command()
def universe():
    """Show the default research universe."""
    _show_universe_table(DEFAULT_UNIVERSE)


def _show_universe_table(tickers: list[str]):
    subthemes = {
        "NVDA": "Compute",
        "AVGO": "Compute",
        "TSM": "Compute",
        "CEG": "Power",
        "VST": "Power",
        "GEV": "Power",
        "PWR": "Infrastructure",
        "ETN": "Infrastructure",
        "APH": "Infrastructure",
        "FIX": "Infrastructure",
        "FCX": "Materials",
        "BHP": "Materials",
        "NXT": "Data Centres",
        "NLR": "ETF",
    }
    table = Table(title="Research Universe")
    table.add_column("Ticker", style="cyan")
    table.add_column("Subtheme")
    for t in tickers:
        table.add_row(t, subthemes.get(t, "Other"))
    console.print(table)


if __name__ == "__main__":
    app()
