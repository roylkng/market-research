"""Bounded research collection, usable outside GitHub Actions without credentials."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.intelligence_runtime import build_report, collect_source, export_report
from marketlab.intelligence_sources import PublicFetcher
from marketlab.intelligence_store import ResearchStore, digest, now_text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("registry/company_intelligence_v2.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--collect", action="store_true", help="Enable bounded public network reads")
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    seed = config["panel_seed"]
    with ResearchStore(args.store) as store:
        store.append("configuration", digest(config), config)
        panel = store.bootstrap_panel(Path(seed["path"]).read_bytes(),
            expected_blob=seed["git_blob"], source_path=seed["path"], panel_id=seed["panel_id"])
        failures = []
        if args.collect:
            fetcher = PublicFetcher()
            for source in config["sources"]:
                result = collect_source(store, source, panel, fetcher)
                print(json.dumps({k: result[k] for k in ("source_id", "status", "completed_at")}),
                      flush=True)
                if result["status"] in {"SOURCE_BLOCKED", "FETCH_FAILED", "PARSE_FAILED", "INTERNAL_ERROR"}:
                    failures.append(source["source_id"])
        report = build_report(store, panel, config, as_of=now_text())
        store.append("report", report["report_sha256"], report)
        export_report(report, args.output)
        print(json.dumps({"company_count": report["company_count"],
              "companies_with_evidence": report["companies_with_extracted_evidence"],
              "active_evidence_count": report["active_evidence_count"],
              "report_sha256": report["report_sha256"], "failed_sources": failures,
              "live_capital_allowed": False}), flush=True)
    # Preserve a usable partial report, but never label partial acquisition a green run.
    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
