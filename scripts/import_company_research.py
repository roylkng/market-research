"""Import explicitly reviewed source excerpts into an existing research panel."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.intelligence_core import EvidenceError
from marketlab.intelligence_reviewed import build_reviewed_report, import_reviewed_capture
from marketlab.intelligence_runtime import export_report
from marketlab.intelligence_store import ResearchStore, now_text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("registry/company_intelligence_v2.json"))
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    bundle = json.loads(args.capture.read_text())
    with ResearchStore(args.store) as store:
        panels = [p for p in store.records("panel") if p["panel_id"] == config["panel_seed"]["panel_id"]]
        if len(panels) != 1:
            raise EvidenceError("Initialize the independently verified research panel first")
        panel = panels[0]
        for capture in bundle["captures"]:
            import_reviewed_capture(store, capture, panel)
        report = build_reviewed_report(store, panel, config, as_of=now_text())
        store.append("report", report["report_sha256"], report)
        export_report(report, args.output)
        print(json.dumps({"reviewed_source_imports": len(report["reviewed_source_imports"]),
                          "active_evidence_count": report["active_evidence_count"],
                          "companies_with_extracted_evidence": report["companies_with_extracted_evidence"],
                          "report_sha256": report["report_sha256"],
                          "automated_source_recovered": False}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
