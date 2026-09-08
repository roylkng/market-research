from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any


def canonical_hash(payload: Any) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def normalized_text(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def abstract_horizon(value: str | None) -> str:
    text = normalized_text(value)
    if not text:
        return "<NONE>"
    text = re.sub(r"\bfy\s*20\d{2}\s*\d{2}\b", "fy <YEAR_RANGE>", text)
    text = re.sub(r"\bfy\s*\d{2}\s*\d{2}\b", "fy <YEAR_RANGE>", text)
    text = re.sub(r"\bfy\s*(?:20)?\d{2}\b", "fy <YEAR>", text)
    text = re.sub(r"\b20\d{2}\b", "<YEAR>", text)
    text = re.sub(r"\bq[1-4]\b", "<QUARTER>", text)
    text = re.sub(r"\bh[12]\b", "<HALF>", text)
    text = re.sub(r"\b\d+(?:\.\d+)?\b", "<N>", text)
    return text


def numeric_target(claim: dict[str, Any]) -> tuple[Any, ...]:
    return (
        claim.get("target_min"),
        claim.get("target_max"),
        normalized_text(claim.get("unit")),
    )


def strict_promise_key(claim: dict[str, Any]) -> tuple[Any, ...]:
    return (
        claim.get("symbol"),
        normalized_text(claim.get("claim_type")),
        normalized_text(claim.get("metric")),
        *numeric_target(claim),
        claim.get("target_deadline"),
        normalized_text(claim.get("target_horizon")),
    )


def broad_promise_key(claim: dict[str, Any]) -> tuple[Any, ...]:
    # Broader than strict fingerprint only to expose possible restatements.
    # It does not mutate or collapse claims.
    return (
        claim.get("symbol"),
        normalized_text(claim.get("metric")),
        *numeric_target(claim),
        claim.get("target_deadline"),
        abstract_horizon(claim.get("target_horizon")),
    )


def days_between(a: str, b: str) -> int:
    return abs((date.fromisoformat(a) - date.fromisoformat(b)).days)


def family_payload(key: tuple[Any, ...], claims: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(claims, key=lambda row: (row["source_date"], row["claim_id"]))
    return {
        "key_sha256": canonical_hash(list(key)),
        "member_count": len(ordered),
        "symbol": ordered[0]["symbol"],
        "source_date_first": ordered[0]["source_date"],
        "source_date_last": ordered[-1]["source_date"],
        "source_span_days": days_between(ordered[0]["source_date"], ordered[-1]["source_date"]),
        "claim_ids": [row["claim_id"] for row in ordered],
        "claim_types": sorted({str(row.get("claim_type")) for row in ordered}),
        "metrics": sorted({str(row.get("metric")) for row in ordered}),
        "target_min": ordered[0].get("target_min"),
        "target_max": ordered[0].get("target_max"),
        "unit": ordered[0].get("unit"),
        "target_deadlines": sorted({str(row.get("target_deadline")) for row in ordered}),
        "target_horizons": sorted({str(row.get("target_horizon")) for row in ordered}),
        "normalized_claims": [row.get("normalized_claim") for row in ordered],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    document = json.loads(args.ledger.read_text(encoding="utf-8"))
    claims = document.get("accepted_claims")
    if not isinstance(claims, list):
        raise SystemExit("frozen ledger accepted_claims is not a list")
    if len(claims) != document.get("accepted_count"):
        raise SystemExit("accepted claim count does not match frozen ledger")
    if len(claims) != 869:
        raise SystemExit(f"expected 869 frozen accepted claims, got {len(claims)}")

    claim_ids = [str(row["claim_id"]) for row in claims]
    if len(claim_ids) != len(set(claim_ids)):
        raise SystemExit("duplicate claim ids in frozen ledger")

    with_deadline = [row for row in claims if row.get("target_deadline")]
    with_horizon = [row for row in claims if row.get("target_horizon")]
    neither = [
        row
        for row in claims
        if not row.get("target_deadline") and not row.get("target_horizon")
    ]
    horizon_only = [
        row
        for row in claims
        if not row.get("target_deadline") and row.get("target_horizon")
    ]

    exact_horizon_counts = Counter(str(row.get("target_horizon")) for row in horizon_only)
    abstract_horizon_counts = Counter(abstract_horizon(row.get("target_horizon")) for row in horizon_only)

    per_company = Counter(str(row["symbol"]) for row in claims)
    per_company_horizon_only = Counter(str(row["symbol"]) for row in horizon_only)

    strict_families: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    broad_families: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for claim in claims:
        strict_families[strict_promise_key(claim)].append(claim)
        broad_families[broad_promise_key(claim)].append(claim)

    strict_repeats = [
        family_payload(key, members)
        for key, members in strict_families.items()
        if len(members) > 1
    ]
    broad_repeats = [
        family_payload(key, members)
        for key, members in broad_families.items()
        if len(members) > 1
    ]
    strict_repeats.sort(key=lambda row: (-row["member_count"], row["symbol"], row["source_date_first"]))
    broad_repeats.sort(key=lambda row: (-row["member_count"], row["symbol"], row["source_date_first"]))

    # Near-repeat exposure: same broad family repeated within one year. This is an
    # audit flag only. No claim is removed by this script.
    broad_within_365 = [row for row in broad_repeats if row["source_span_days"] <= 365]

    output_unsigned = {
        "schema_version": 1,
        "audit_id": "H003-A001",
        "input_ledger_sha256": document.get("ledger_sha256"),
        "accepted_claim_count": len(claims),
        "claims_with_canonical_deadline": len(with_deadline),
        "claims_with_target_horizon": len(with_horizon),
        "claims_horizon_only": len(horizon_only),
        "claims_with_neither_deadline_nor_horizon": len(neither),
        "unique_horizon_only_text_count": len(exact_horizon_counts),
        "unique_horizon_only_abstract_pattern_count": len(abstract_horizon_counts),
        "exact_horizon_only_counts": [
            {"horizon": key, "count": count}
            for key, count in sorted(exact_horizon_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "abstract_horizon_only_counts": [
            {"pattern": key, "count": count}
            for key, count in sorted(abstract_horizon_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "company_claim_counts": [
            {
                "symbol": symbol,
                "accepted_claims": count,
                "horizon_only_claims": per_company_horizon_only.get(symbol, 0),
            }
            for symbol, count in sorted(per_company.items(), key=lambda item: (-item[1], item[0]))
        ],
        "strict_repeated_promise_family_count": len(strict_repeats),
        "strict_repeated_promise_claim_count": sum(row["member_count"] for row in strict_repeats),
        "broad_repeated_promise_family_count": len(broad_repeats),
        "broad_repeated_promise_claim_count": sum(row["member_count"] for row in broad_repeats),
        "broad_repeated_within_365d_family_count": len(broad_within_365),
        "strict_repeated_families": strict_repeats,
        "broad_repeated_families": broad_repeats,
        "live_capital_allowed": False,
        "outcome_data_accessed": False,
        "note": (
            "Outcome-blind audit only. Repeated-family flags are diagnostics, not "
            "automatic duplicate decisions. A collapse/supersession rule must be frozen "
            "separately before any claim outcomes are scored."
        ),
    }
    output = {**output_unsigned, "audit_sha256": canonical_hash(output_unsigned)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    console = {
        key: output[key]
        for key in (
            "audit_id",
            "accepted_claim_count",
            "claims_with_canonical_deadline",
            "claims_with_target_horizon",
            "claims_horizon_only",
            "claims_with_neither_deadline_nor_horizon",
            "unique_horizon_only_text_count",
            "unique_horizon_only_abstract_pattern_count",
            "strict_repeated_promise_family_count",
            "strict_repeated_promise_claim_count",
            "broad_repeated_promise_family_count",
            "broad_repeated_promise_claim_count",
            "broad_repeated_within_365d_family_count",
            "audit_sha256",
        )
    }
    print(json.dumps(console, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
