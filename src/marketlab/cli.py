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

    frame = pd.read_csv(csv_path)
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

    frame = pd.read_csv(csv_path)
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
