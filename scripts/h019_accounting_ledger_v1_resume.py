"""Resume H019 accounting-ledger v1 from the frozen run-1 parent artifact.

This script never rebuilds the historical symbol sample or annual-report metadata
selection. It consumes the verified parent evidence, reacquires exactly the 157
metadata-frozen report URLs, fails individual malformed reports closed, and then
builds the point-in-time observation ledger with the unchanged v3 parser.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path

from pypdf.errors import PdfReadError

import h019_accounting_ledger_v1 as ledger
import h019_annual_report_feasibility as source
import h019_numeric_extraction_audit as v2
import h019_numeric_extraction_audit_v3 as v3
from marketlab.nse import NSEClient

PARENT_RUN_ID = 34363988787
PARENT_ARTIFACT_ID = 10109147020
PARENT_ARTIFACT_NAME = "h019-accounting-ledger-v1-34363988787"
PARENT_ARTIFACT_DIGEST = "sha256:491d3a77d7bc63935db42d4672fca92638fbc14ad8628c47e6ddeb6e80755ba0"

FROZEN_FILES = {
    "frozen-symbol-sample.json": "0b46d031d76ed3d7db3ff47a9aeabf8973e0cc017e429d0b5f0ccc703f12675a",
    "listing-manifest.json": "164d5d84abcf4bc440487e5482cd7d02df738fb00bb95670795690208dd0bb31",
    "annual-report-api-manifest.json": "f45be1b5c343a781f489379136f38dd39dcc4fe7ba2479a1a09e30da504659c7",
    "annual-report-metadata.json": "e71bb11d7cb46a2970d5f8a9b10a2547ede09ccfea9305306120e245fab36b07",
    "metadata-frozen-report-selection.json": "b61333133ee1c9191b524b058ebaacca989cef862a9063168928b6314d53586e",
}
FROZEN_SELECTION_CANONICAL_SHA256 = "8c61746c48efabc7bbeb54dd3dcf5f998042432edd34099fb8edd9ffbdca9cd1"
FROZEN_REPORT_COUNT = 157
FROZEN_SYMBOLS_WITH_REPORTS = 81
FROZEN_REPORT_COUNT_DISTRIBUTION = {0: 19, 1: 5, 2: 76}
FROZEN_GROUP_REPORT_ROWS = {
    "SURVIVOR_PROXY": 100,
    "EXIT_PROXY": 47,
    "NEW_PROXY": 10,
}
EXPECTED_GROUP_COUNTS = {
    "SURVIVOR_PROXY": 50,
    "EXIT_PROXY": 25,
    "NEW_PROXY": 25,
}
FAIL_CLOSED_EXCEPTIONS = (KeyError, OSError, TypeError, ValueError, PdfReadError)


def dump(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_json_sha256(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def verify_parent(parent: Path) -> dict[str, object]:
    verified_hashes: dict[str, str] = {}
    for name, expected in FROZEN_FILES.items():
        path = parent / name
        if not path.is_file():
            raise ValueError(f"missing frozen parent evidence: {name}")
        actual = file_sha256(path)
        if actual != expected:
            raise ValueError(f"frozen parent evidence hash mismatch for {name}: {actual}")
        verified_hashes[name] = actual

    sample = json.loads((parent / "frozen-symbol-sample.json").read_text())
    api_manifest = json.loads((parent / "annual-report-api-manifest.json").read_text())
    selection = json.loads((parent / "metadata-frozen-report-selection.json").read_text())

    groups = sample.get("groups")
    if not isinstance(groups, dict):
        raise TypeError("frozen sample groups missing")
    for group, count in EXPECTED_GROUP_COUNTS.items():
        symbols = groups.get(group)
        if not isinstance(symbols, list) or len(symbols) != count:
            raise ValueError(f"frozen group mismatch for {group}")
    all_symbols = [symbol for group in EXPECTED_GROUP_COUNTS for symbol in groups[group]]
    if len(all_symbols) != 100 or len(set(all_symbols)) != 100:
        raise ValueError("frozen parent sample is not exactly 100 distinct symbols")

    if len(api_manifest) != 100 or any(row.get("status") != "OK" for row in api_manifest):
        raise ValueError("frozen annual-report API manifest is not 100/100 OK")
    if len(selection) != FROZEN_REPORT_COUNT:
        raise ValueError(f"frozen report selection is not {FROZEN_REPORT_COUNT} records")
    if canonical_json_sha256(selection) != FROZEN_SELECTION_CANONICAL_SHA256:
        raise ValueError("frozen report selection canonical hash mismatch")

    selected_by_symbol = Counter(str(row["symbol"]) for row in selection)
    distribution = Counter(selected_by_symbol.get(str(symbol), 0) for symbol in all_symbols)
    if dict(sorted(distribution.items())) != FROZEN_REPORT_COUNT_DISTRIBUTION:
        raise ValueError(f"frozen per-symbol report-count distribution changed: {dict(distribution)}")
    if len(selected_by_symbol) != FROZEN_SYMBOLS_WITH_REPORTS:
        raise ValueError("frozen symbols-with-report count changed")
    if max(selected_by_symbol.values(), default=0) > ledger.MAX_REPORT_YEARS:
        raise ValueError("frozen selection contains more than two reports for a symbol")

    group_rows = Counter(str(row["group"]) for row in selection)
    if dict(group_rows) != FROZEN_GROUP_REPORT_ROWS:
        raise ValueError(f"frozen report rows by group changed: {dict(group_rows)}")
    if any(datetime.fromisoformat(str(row["available_at"])) > ledger.CUTOFF for row in selection):
        raise ValueError("future-dated report entered frozen selection")

    keys = [
        (str(row["symbol"]), int(row["to_year"]), str(row["report_url"]))
        for row in selection
    ]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate records in frozen report selection")

    return {
        "parent_run_id": PARENT_RUN_ID,
        "parent_artifact_id": PARENT_ARTIFACT_ID,
        "parent_artifact_name": PARENT_ARTIFACT_NAME,
        "parent_artifact_digest": PARENT_ARTIFACT_DIGEST,
        "verified_frozen_file_hashes": verified_hashes,
        "selection_canonical_sha256": FROZEN_SELECTION_CANONICAL_SHA256,
        "frozen_symbol_count": 100,
        "frozen_report_count": len(selection),
        "symbols_with_selected_reports": len(selected_by_symbol),
        "report_count_distribution": {str(key): value for key, value in sorted(distribution.items())},
        "report_rows_by_group": dict(group_rows),
        "status": "PARENT_FROZEN_FILES_VERIFIED",
    }


def copy_frozen_parent_evidence(parent: Path, out: Path) -> None:
    for name in FROZEN_FILES:
        shutil.copy2(parent / name, out / name)


def parser_failed_closed(
    frozen: dict[str, object],
    retained: dict[str, object],
    pdf_sha256: str,
    exc: BaseException,
) -> dict[str, object]:
    return {
        "status": "PARSER_FAILED_CLOSED",
        "symbol": frozen["symbol"],
        "group": frozen["group"],
        "company": frozen.get("company"),
        "from_year": frozen["from_year"],
        "to_year": frozen["to_year"],
        "available_at": frozen["available_at"],
        "report_url": frozen["report_url"],
        "report_sha256": retained["sha256"],
        "pdf_sha256": pdf_sha256,
        "api_source_sha256": frozen["api_source_sha256"],
        "exception_type": type(exc).__name__,
        "error": str(exc)[:1000],
        "fallback_used": False,
        "protocol_version": "ledger-v1-resume",
    }


def safe_extract_report(
    parser_row: dict[str, object],
    frozen: dict[str, object],
    retained: dict[str, object],
    pdf_sha256: str,
    root: Path,
) -> dict[str, object]:
    try:
        extraction = v3.extract_report(parser_row, root)
    except FAIL_CLOSED_EXCEPTIONS as exc:
        return parser_failed_closed(frozen, retained, pdf_sha256, exc)
    extraction["available_at"] = frozen["available_at"]
    extraction["api_source_sha256"] = frozen["api_source_sha256"]
    extraction["fallback_used"] = False
    extraction["protocol_version"] = "ledger-v1-resume"
    return extraction


def provenance_complete(row: dict[str, object]) -> bool:
    return ledger.provenance_complete(row)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen-root", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    parent = Path(args.frozen_root)
    root = Path(args.out)
    root.mkdir(parents=True, exist_ok=True)

    lineage = verify_parent(parent)
    copy_frozen_parent_evidence(parent, root)
    dump(root / "parent-artifact-lineage.json", lineage)

    sample_payload = json.loads((parent / "frozen-symbol-sample.json").read_text())
    sample = sample_payload["groups"]
    api_manifest = json.loads((parent / "annual-report-api-manifest.json").read_text())
    frozen_report_rows = json.loads((parent / "metadata-frozen-report-selection.json").read_text())

    v3.install_patches()
    client = NSEClient(timeout=30, attempts=4)

    report_manifest: list[dict[str, object]] = []
    extraction_rows: list[dict[str, object]] = []
    report_by_key: dict[tuple[str, int, str], dict[str, object]] = {}
    attempted_keys: list[tuple[str, int, str]] = []
    fallback_count = 0

    for number, frozen in enumerate(frozen_report_rows, 1):
        row = dict(frozen)
        key = (str(row["symbol"]), int(row["to_year"]), str(row["report_url"]))
        attempted_keys.append(key)

        raw, download = source.archive_download(client, str(row["report_url"]))
        if raw is None:
            report_manifest.append({**row, **download, "fallback_used": False})
            extraction_rows.append(
                {
                    "status": "REPORT_DOWNLOAD_FAILED_CLOSED",
                    "symbol": row["symbol"],
                    "group": row["group"],
                    "company": row.get("company"),
                    "from_year": row["from_year"],
                    "to_year": row["to_year"],
                    "available_at": row["available_at"],
                    "report_url": row["report_url"],
                    "api_source_sha256": row["api_source_sha256"],
                    "fallback_used": False,
                    "protocol_version": "ledger-v1-resume",
                }
            )
            continue

        retained = source.retain(
            root,
            raw,
            url=str(row["report_url"]),
            kind="ledger-resume-annual-report-container",
        )
        pdf_raw, container = source.extract_pdf_bytes(raw, str(row["report_url"]))
        manifest_row = {**row, **download, **retained, **container, "fallback_used": False}
        if pdf_raw is None:
            manifest_row["status"] = "PDF_CONTAINER_UNUSABLE"
            report_manifest.append(manifest_row)
            extraction_rows.append(
                {
                    "status": "PDF_CONTAINER_FAILED_CLOSED",
                    "symbol": row["symbol"],
                    "group": row["group"],
                    "company": row.get("company"),
                    "from_year": row["from_year"],
                    "to_year": row["to_year"],
                    "available_at": row["available_at"],
                    "report_url": row["report_url"],
                    "report_sha256": retained["sha256"],
                    "api_source_sha256": row["api_source_sha256"],
                    "fallback_used": False,
                    "protocol_version": "ledger-v1-resume",
                }
            )
            continue

        pdf_digest = v2.sha256(pdf_raw)
        manifest_row["pdf_sha256"] = pdf_digest
        manifest_row["status"] = "RETAINED"
        report_manifest.append(manifest_row)

        parser_row = {
            **row,
            "sha256": retained["sha256"],
            "raw_path": retained["raw_path"],
            "pdf_sha256": pdf_digest,
        }
        report_by_key[key] = parser_row
        extraction_rows.append(
            safe_extract_report(parser_row, row, retained, pdf_digest, root)
        )

        if number % 20 == 0:
            print(f"H019 resumed ledger reports {number}/{len(frozen_report_rows)}", flush=True)

    if len(attempted_keys) != FROZEN_REPORT_COUNT or len(set(attempted_keys)) != FROZEN_REPORT_COUNT:
        raise ValueError("resume did not attempt exactly 157 unique frozen reports")
    fallback_count += sum(bool(row.get("fallback_used")) for row in report_manifest)
    fallback_count += sum(bool(row.get("fallback_used")) for row in extraction_rows)

    dump(root / "report-source-manifest.json", report_manifest)
    dump(root / "report-extractions.json", extraction_rows)

    observations = ledger.build_observations(extraction_rows, report_by_key)
    resolved, ambiguities = ledger.resolve_as_of(observations, ledger.CUTOFF)
    history = ledger.symbol_history_coverage(resolved, sample)
    dump(root / "accounting-observations.json", observations)
    dump(root / "asof-resolved-facts.json", resolved)
    dump(root / "resolver-ambiguities.json", ambiguities)
    dump(root / "symbol-history-coverage.json", history)

    selected_by_symbol = Counter(str(row["symbol"]) for row in frozen_report_rows)
    report_status_by_group = {
        group: dict(Counter(str(row["status"]) for row in report_manifest if row["group"] == group))
        for group in ledger.GROUP_COUNTS
    }
    extraction_status_by_group = {
        group: dict(Counter(str(row["status"]) for row in extraction_rows if row["group"] == group))
        for group in ledger.GROUP_COUNTS
    }
    current_core_by_fact = {
        fact: sum(
            row.get("status") == "EXTRACTED"
            and isinstance(row.get("facts"), dict)
            and isinstance(row["facts"].get(fact), dict)
            and "current_inr" in row["facts"][fact]
            for row in extraction_rows
        )
        for fact in ledger.CORE_FACTS
    }
    prior_core_by_fact = {
        fact: sum(
            row.get("status") == "EXTRACTED"
            and isinstance(row.get("facts"), dict)
            and isinstance(row["facts"].get(fact), dict)
            and "prior_inr" in row["facts"][fact]
            for row in extraction_rows
        )
        for fact in ledger.CORE_FACTS
    }
    balance_pass = sum(
        isinstance(row.get("balance_identity"), dict)
        and bool(row["balance_identity"].get("current_pass"))
        for row in extraction_rows
    )
    observation_counts_by_fact = dict(Counter(str(row["fact"]) for row in observations))
    observation_counts_by_year = dict(Counter(str(row["fiscal_year_to"]) for row in observations))
    resolved_ids = {str(row["resolved_from_observation_id"]) for row in resolved}
    observation_ids = {str(row["observation_id"]) for row in observations}

    successful_report_hashes = all(
        row.get("status") != "RETAINED"
        or (bool(row.get("sha256")) and bool(row.get("pdf_sha256")))
        for row in report_manifest
    )
    selected_dates_valid = all(
        datetime.fromisoformat(str(row["available_at"])) <= ledger.CUTOFF
        for row in frozen_report_rows
    )
    provenance_ok = all(provenance_complete(row) for row in observations)
    resolved_references_ok = resolved_ids <= observation_ids
    no_future_resolved = all(
        datetime.fromisoformat(str(row["available_at"])) <= ledger.CUTOFF for row in resolved
    )
    parent_api_ok = len(api_manifest) == 100 and all(row.get("status") == "OK" for row in api_manifest)

    gates = {
        "parent_frozen_files_exact": lineage["status"] == "PARENT_FROZEN_FILES_VERIFIED",
        "exactly_100_frozen_symbols": sum(len(values) for values in sample.values()) == 100,
        "exact_group_counts": all(len(sample[group]) == count for group, count in EXPECTED_GROUP_COUNTS.items()),
        "parent_annual_report_api_100_of_100_ok": parent_api_ok,
        "no_listing_or_metadata_reacquisition": True,
        "exactly_157_frozen_reports_attempted_once": len(attempted_keys) == len(set(attempted_keys)) == 157,
        "zero_fallback_or_replacement_reports": fallback_count == 0,
        "successful_report_sources_hashed": successful_report_hashes,
        "selected_metadata_not_after_cutoff": selected_dates_valid,
        "max_two_report_years_per_symbol": all(count <= ledger.MAX_REPORT_YEARS for count in selected_by_symbol.values()),
        "observation_provenance_complete": provenance_ok,
        "resolved_facts_reference_observations": resolved_references_ok,
        "no_future_observation_resolved": no_future_resolved,
        "ambiguities_not_silently_resolved": all(
            not set(row["candidate_observation_ids"]) & resolved_ids for row in ambiguities
        ),
        "source_only_no_outcome_state": True,
    }

    core_history_count = sum(bool(row["three_year_core"]) for row in history)
    cfo_history_count = sum(bool(row["three_year_core_plus_cfo"]) for row in history)
    parser_failures = sum(row.get("status") == "PARSER_FAILED_CLOSED" for row in extraction_rows)
    no_text = sum(row.get("status") == "NO_TEXT_NO_OCR" for row in extraction_rows)

    summary = {
        "status": "H019_ACCOUNTING_LEDGER_V1_RESUMED_COVERAGE_ONLY",
        "cutoff": ledger.CUTOFF.isoformat(),
        "market_outcomes_opened": False,
        "live_capital_allowed": False,
        "parent_lineage": lineage,
        "frozen_symbol_count": 100,
        "frozen_group_counts": EXPECTED_GROUP_COUNTS,
        "selected_report_records": len(frozen_report_rows),
        "symbols_with_zero_selected_reports": sum(selected_by_symbol[str(symbol)] == 0 for group in sample.values() for symbol in group),
        "symbols_with_one_selected_report": sum(selected_by_symbol[str(symbol)] == 1 for group in sample.values() for symbol in group),
        "symbols_with_two_selected_reports": sum(selected_by_symbol[str(symbol)] == 2 for group in sample.values() for symbol in group),
        "report_status_by_group": report_status_by_group,
        "extraction_status_by_group": extraction_status_by_group,
        "parser_failed_closed_reports": parser_failures,
        "no_text_no_ocr_reports": no_text,
        "current_core_fact_reports": current_core_by_fact,
        "prior_core_fact_reports": prior_core_by_fact,
        "balance_identity_current_pass_reports": balance_pass,
        "accounting_observations": len(observations),
        "resolved_facts": len(resolved),
        "resolver_ambiguities": len(ambiguities),
        "observation_counts_by_fact": observation_counts_by_fact,
        "observation_counts_by_fiscal_year_to": observation_counts_by_year,
        "three_year_core_history_count": core_history_count,
        "three_year_core_history_rate": ledger.rate(core_history_count, 100),
        "three_year_core_plus_cfo_count": cfo_history_count,
        "three_year_core_plus_cfo_rate": ledger.rate(cfo_history_count, 100),
        "coverage_by_group": ledger.group_coverage(history),
        "integrity_gates": gates,
        "integrity_pass": all(gates.values()),
    }
    dump(root / "ledger-summary.json", summary)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
