from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg005_context import EXPECTED_SYMBOLS, build_hg005_context


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"JSON payload must be an object: {path}")
    return payload


def _shareholding_raw(
    *,
    gf001: dict,
    artifact_root: Path,
) -> tuple[dict[str, bytes], dict[str, bytes]]:
    rows = gf001.get("rows")
    if not isinstance(rows, list):
        raise TypeError("HG005 GF001 rows must be a list")
    by_symbol = {
        str(row.get("symbol") or "").upper(): row
        for row in rows
        if isinstance(row, dict)
    }

    latest_raw: dict[str, bytes] = {}
    prior_raw: dict[str, bytes] = {}
    for symbol in sorted(EXPECTED_SYMBOLS):
        row = by_symbol.get(symbol)
        if not isinstance(row, dict):
            raise ValueError(f"{symbol}: GF001 row unavailable")

        latest = row.get("latest")
        if not isinstance(latest, dict):
            raise ValueError(f"{symbol}: latest GF001 row unavailable")
        latest_sha = str(latest.get("raw_sha256") or "")
        if not latest_sha:
            raise ValueError(f"{symbol}: latest GF001 raw SHA unavailable")
        latest_path = artifact_root / "raw" / "xbrl" / "sha256" / f"{latest_sha}.xml"
        latest_raw[symbol] = latest_path.read_bytes()

        prior = row.get("prior")
        if isinstance(prior, dict):
            prior_sha = str(prior.get("raw_sha256") or "")
            if prior_sha:
                prior_path = (
                    artifact_root / "raw" / "xbrl" / "sha256" / f"{prior_sha}.xml"
                )
                prior_raw[symbol] = prior_path.read_bytes()

    return latest_raw, prior_raw


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hg004-l002", type=Path, required=True)
    parser.add_argument("--hg004-l001", type=Path, required=True)
    parser.add_argument("--ss001", type=Path, required=True)
    parser.add_argument("--gf001", type=Path, required=True)
    parser.add_argument("--gf001-artifact-root", type=Path, required=True)
    parser.add_argument("--fa001", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    hg004_l002 = _load(args.hg004_l002)
    hg004_l001 = _load(args.hg004_l001)
    ss001 = _load(args.ss001)
    gf001 = _load(args.gf001)
    fa001 = _load(args.fa001)
    latest_raw, prior_raw = _shareholding_raw(
        gf001=gf001,
        artifact_root=args.gf001_artifact_root,
    )

    output = build_hg005_context(
        hg004_l002=hg004_l002,
        hg004_l001=hg004_l001,
        ss001=ss001,
        gf001=gf001,
        fa001=fa001,
        latest_shareholding_raw=latest_raw,
        prior_shareholding_raw=prior_raw,
    )

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "hg005-d001-context.json").write_text(
        json.dumps(
            output,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    summary = {key: value for key, value in output.items() if key != "rows"}
    (args.out / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
