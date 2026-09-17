"""Discover bounded news snapshots and join them into the existing company store."""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from marketlab.intelligence_discovery import (
    build_discovery_report,
    export_discovery_report,
    run_discovery,
    verify_discovery,
)
from marketlab.intelligence_http import PublicFetcher
from marketlab.intelligence_identity import identity_members_from_udiff
from marketlab.intelligence_store import ResearchStore, now_text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("registry/company_news_discovery_v2.json"))
    parser.add_argument("--company-config", type=Path, default=Path("registry/company_intelligence_v2.json"))
    parser.add_argument("--collect", action="store_true")
    parser.add_argument("--identity-udiff", type=Path)
    parser.add_argument("--identity-session")
    args = parser.parse_args()
    if bool(args.identity_udiff) != bool(args.identity_session):
        parser.error("--identity-udiff and --identity-session must be supplied together")
    config = json.loads(args.config.read_text())
    company = json.loads(args.company_config.read_text())
    seed = company["panel_seed"]
    run = None
    with ResearchStore(args.store) as store:
        panel = store.bootstrap_panel(Path(seed["path"]).read_bytes(), expected_blob=seed["git_blob"],
                                     source_path=seed["path"], panel_id=seed["panel_id"])
        discovery_panel = panel
        if args.identity_udiff:
            identity_members = identity_members_from_udiff(
                args.identity_udiff.read_bytes(),
                session_date=date.fromisoformat(args.identity_session),
                deep_members=panel["members"],
            )
            discovery_panel = {**panel, "members": identity_members,
                               "identity_session": args.identity_session,
                               "identity_scope": "BROAD_PRIOR_NSE_EQ_COMPANY_IDENTITIES"}
        if args.collect:
            run = run_discovery(store, discovery_panel, config, PublicFetcher(read_timeout=12))
        proof = verify_discovery(store, discovery_panel)
        report = build_discovery_report(store, panel, company, config, as_of=now_text())
        store.append("report", report["report_sha256"], report)
        export_discovery_report(report, args.output)
        news = report["news_discovery"]
        print(json.dumps({"report_sha256": report["report_sha256"], "as_of": report["as_of"],
            "items": news["item_count"], "documents": news["document_count"],
            "panel_mentions": news["panel_companies_with_mentions"],
            "external_unverified_symbols": news["unverified_external_symbols"],
            "identity_scope": discovery_panel.get("identity_scope", "DEEP_PANEL_ONLY"),
            "identity_count": len(discovery_panel["members"]),
            "source_status_counts": news["source_status_counts"], "proof": proof,
            "run_status": run["status"] if run else "OFFLINE_REPORT", "forecast": None}), flush=True)
    return 2 if run and run["status"] == "PARTIAL_FAILURE" else 0


if __name__ == "__main__":
    raise SystemExit(main())
