from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import pandas as pd
import typer

from marketlab.claims import ClaimLedgerError, load_claim_ledger
from marketlab.evaluation import (
    RegistryError,
    evaluate_binary_groups,
    evaluate_continuous_signal,
    require_valid_registry,
    winner_concentration,
)
from marketlab.events import EventParseError, EventStore
from marketlab.nse import NSEAcquisitionError, NSEClient
from marketlab.universe import UniverseError, build_universe_snapshot

app = typer.Typer(help="Reproducible market-research utilities.", no_args_is_help=True)

EXAMPLE_FIXTURE = Path("data/fixtures/h002_feasibility.csv")


def _read_csv_or_exit(csv_path: Path, *, required_columns: list[str]) -> pd.DataFrame:
    if not csv_path.exists() or not csv_path.is_file():
        typer.echo(f"input CSV not found: {csv_path}", err=True)
        typer.echo(f"runnable example: {EXAMPLE_FIXTURE}", err=True)
        raise typer.Exit(code=2)

    try:
        frame = pd.read_csv(csv_path)
    except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        typer.echo(f"could not read CSV {csv_path}: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    missing = [column for column in required_columns if column not in frame.columns]
    if missing:
        available = ", ".join(str(column) for column in frame.columns) or "<none>"
        typer.echo(f"CSV is missing required column(s): {', '.join(missing)}", err=True)
        typer.echo(f"available columns: {available}", err=True)
        raise typer.Exit(code=2)

    return frame


@app.command("validate-registry")
def validate_registry(path: Path) -> None:
    """Validate hypothesis-registry invariants."""

    try:
        document = require_valid_registry(path)
    except RegistryError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(
        f"registry valid: {len(document['hypotheses'])} hypotheses; live capital disabled"
    )


@app.command("snapshot-universe")
def snapshot_universe(
    output: Annotated[Path, typer.Option(help="Output JSON path")],
    cohort_id: Annotated[str, typer.Option(help="Immutable earnings-cohort identifier")],
    selection_size: Annotated[int, typer.Option(min=1, max=200)] = 100,
) -> None:
    """Freeze the mechanical H002 research universe from current NSE metadata."""

    client = NSEClient()
    try:
        index_payload = client.index_snapshot("NIFTY 200")
        snapshot = build_universe_snapshot(
            index_payload,
            client.quote_equity,
            cohort_id=cohort_id,
            selection_size=selection_size,
        )
    except (NSEAcquisitionError, UniverseError) as exc:
        typer.echo(f"universe snapshot failed: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(snapshot.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    typer.echo(
        f"wrote {snapshot.selection_size} companies to {output}; sha256={snapshot.sha256}"
    )


@app.command("reconstruct-event")
def reconstruct_event(
    input_file: Path,
    source_url: Annotated[str, typer.Option(help="Original filing URL represented by the file")],
    store: Annotated[Path, typer.Option(help="Local content-addressed research store")] = Path(
        ".marketlab"
    ),
) -> None:
    """Reconstruct one historical Ind-AS event from local source bytes.

    This command always records HISTORICAL_RECONSTRUCTION. It cannot create a
    prospective H002 observation.
    """

    if not input_file.exists() or not input_file.is_file():
        typer.echo(f"input filing not found: {input_file}", err=True)
        raise typer.Exit(code=2)
    try:
        raw = input_file.read_bytes()
        event, created = EventStore(store).reconstruct_bytes(raw, source_url=source_url)
    except (OSError, UnicodeDecodeError, EventParseError) as exc:
        typer.echo(f"historical reconstruction failed: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    typer.echo(
        json.dumps(
            {
                "created": created,
                "event": event.to_dict(),
            },
            indent=2,
            sort_keys=True,
        )
    )


@app.command("delivery-report")
def delivery_report(
    ledger_path: Path,
    symbol: Annotated[str, typer.Option(help="NSE symbol to report")],
) -> None:
    """Report historical management promise-to-delivery evidence for one company."""

    if not ledger_path.exists() or not ledger_path.is_file():
        typer.echo(f"claim ledger not found: {ledger_path}", err=True)
        raise typer.Exit(code=2)
    try:
        ledger = load_claim_ledger(ledger_path)
    except (OSError, ClaimLedgerError) as exc:
        typer.echo(f"invalid claim ledger: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    report = ledger.company_report(symbol)
    if report["claim_count"] == 0:
        typer.echo(f"no claims found for symbol: {symbol.upper()}", err=True)
        raise typer.Exit(code=2)
    typer.echo(json.dumps(report, indent=2, sort_keys=True))


@app.command("evaluate-signal")
def evaluate_signal(
    csv_path: Path,
    signal_col: str = typer.Option(..., help="Continuous signal column"),
    excess_col: str = typer.Option(..., help="Benchmark-relative return column"),
) -> None:
    """Evaluate a continuous signal against subsequent excess return."""

    frame = _read_csv_or_exit(csv_path, required_columns=[signal_col, excess_col])
    result = evaluate_continuous_signal(
        frame,
        signal_col=signal_col,
        excess_return_col=excess_col,
    )
    typer.echo(json.dumps(result.to_dict(), indent=2, sort_keys=True))


@app.command("evaluate-binary")
def evaluate_binary(
    csv_path: Path,
    group_col: str = typer.Option(...),
    excess_col: str = typer.Option(...),
    positive_value: str = typer.Option("Positive UE"),
    negative_value: str = typer.Option("Negative UE"),
    top_n_winners: int = typer.Option(2, min=1),
) -> None:
    """Evaluate two pre-defined groups and expose winner dependence."""

    frame = _read_csv_or_exit(csv_path, required_columns=[group_col, excess_col])
    result = evaluate_binary_groups(
        frame,
        group_col=group_col,
        excess_return_col=excess_col,
        positive_value=positive_value,
        negative_value=negative_value,
    )
    concentration = winner_concentration(frame[excess_col], top_n=top_n_winners)
    typer.echo(
        json.dumps(
            {
                "group_evaluation": result.to_dict(),
                "winner_concentration": concentration,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    app()
