"""Discover bounded news snapshots and join them into the existing company store."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.intelligence_discovery import (
    build_discovery_report,
    export_discovery_report,
    run_discovery,
    verify_discovery,
)
from marketlab.intelligence_http import PublicFetcher
from marketlab.intelligence_store import ResearchStore, now_text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("registry/company_news_discovery_v2.json"))
    parser.add_argument("--company-config", type=Path, default=Path("registry/company_intelligence_v2.json"))
    parser.add_argument("--collect", action="store_true")
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    company = json.loads(args.company_config.read_text())
    seed = company["panel_seed"]
    run = None
    with ResearchStore(args.store) as store:
        panel = store.bootstrap_panel(Path(seed["path"]).read_bytes(), expected_blob=seed["git_blob"],
                                     source_path=seed["path"], panel_id=seed["panel_id"])
        if args.collect:
            run = run_discovery(store, panel, config, PublicFetcher(read_timeout=12))
        proof = verify_discovery(store, panel)
        report = build_discovery_report(store, panel, company, config, as_of=now_text())
        store.append("report", report["report_sha256"], report)
        export_discovery_report(report, args.output)
        news = report["news_discovery"]
        print(json.dumps({"report_sha256": report["report_sha256"], "as_of": report["as_of"],
            "items": news["item_count"], "documents": news["document_count"],
            "panel_mentions": news["panel_companies_with_mentions"],
            "external_unverified_symbols": news["unverified_external_symbols"],
            "source_status_counts": news["source_status_counts"], "proof": proof,
            "run_status": run["status"] if run else "OFFLINE_REPORT", "forecast": None}), flush=True)
    return 2 if run and run["status"] == "PARTIAL_FAILURE" else 0


if __name__ == "__main__":
    raise SystemExit(main())
