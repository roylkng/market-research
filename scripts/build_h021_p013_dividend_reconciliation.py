"""Publish an additive, source-verified H021 first-cohort dividend risk delta.

The original 9 Oct pre-entry risk alert is IMMUTABLE. A later, original
8 Oct VEDL PDF was retrieved on 12 Oct *after* the planned H021 open.
Never rewrite that timing or promote ex-date/entitlement/total returns.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.h021_p013_dividend_reconciliation import (
    build_vedl_source_delta,
    load_original_sources,
    require_total_return_permission,
)


def _canonical_json(result: dict) -> str:
    return json.dumps(
        result, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    ) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify-existing", action="store_true")
    parser.add_argument("--require-return-clearance", action="store_true")
    args = parser.parse_args()
    if args.verify_existing and args.out is None:
        parser.error("--verify-existing requires --out")

    risk, receipt, intent, provenance = load_original_sources(args.repo_root)
    result = build_vedl_source_delta(risk, receipt, intent, provenance)
    if args.require_return_clearance:
        require_total_return_permission(result)

    encoded = _canonical_json(result)
    if args.out is not None:
        if args.verify_existing:
            if args.out.read_text(encoding="utf-8") != encoded:
                raise ValueError("original-source dividend risk delta changed")
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as dest:
                dest.write(encoded)

    print(json.dumps({
        "evidence_delta_id": result["evidence_delta_id"],
        "original_h021_selection_unchanged": result["original_p003_selected_names_unchanged"],
        "frozen_h021_symbol_count": result["frozen_selected_count"],
        "issuer_declaration_source_verified": result[
            "dividend_declaration_original_source_confirmed_count"
        ],
        "dividend_ex_date_complete": result[
            "VEDL_ex_date_original_exchange_action_census_complete"
        ],
        "dividend_entitlement_calculated": result["cash_entitlement_and_payment_calculated"],
        "returns_opened": result["twenty_or_sixty_session_returns_opened"],
        "live_capital_allowed": result["live_capital_allowed"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
