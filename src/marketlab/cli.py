from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import typer

from marketlab.evaluation import (
    RegistryError,
    evaluate_binary_groups,
    evaluate_continuous_signal,
    require_valid_registry,
    winner_concentration,
)

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
