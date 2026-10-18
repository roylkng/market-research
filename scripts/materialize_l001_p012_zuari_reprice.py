"""Reprice issuer-listed holdings with exact October 15 NSE original UDiFF."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

from marketlab.l001_p012_zuari_reprice import from_original_documents

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_UDIFF = ROOT / (
    "research/prospective/h021/daily-prices/raw/sha256/"
    "3d1c7039e2c70868cc44b51d1f9e4b0f942afc0575fe8c4a524aed9e01eac3e8.zip"
)


def materialize(artifact_dir: Path) -> dict:
    p011 = artifact_dir / "github-actions-artifact-12132536549.zip"
    p004 = artifact_dir / "github-actions-artifact-12111414537.zip"
    with zipfile.ZipFile(p011) as outer:
        embedded = outer.read("l001-p011-six-original-issuer-documents.zip")
    import io

    with zipfile.ZipFile(io.BytesIO(embedded)) as inner:
        deck = inner.read("original_pdf/zuari_q1_fy27_issuer_investor_deck.pdf")
    with zipfile.ZipFile(p004) as original:
        shares = json.loads(original.read("l001-p004-all100-original-audit.json"))
    return from_original_documents(ORIGINAL_UDIFF.read_bytes(), deck, shares)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    out = materialize(args.artifact_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "issuer": out["issuer"],
        "repriced_listed_holdings_cr": out["oct15_pro_forma_portfolio_mark_cr"],
        "change_from_june_fraction": out[
            "oct15_pro_forma_portfolio_change_from_june_reported_fraction"
        ],
        "net_borrowings_old_march_cr": out["old_march_net_debt_cr"],
        "stale_debt_residual_cr": out[
            "oct15_pro_forma_portfolio_less_old_march_net_debt_cr"
        ],
        "asset_haircut_to_eliminate_discount": out[
            "additional_markdown_asset_haircut_needed_to_match_basic_cap"
        ],
        "report_sha256": out["report_sha256"],
        "investable": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
